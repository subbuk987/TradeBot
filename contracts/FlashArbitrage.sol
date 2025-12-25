// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@aave/v3-core/contracts/flashloan/base/FlashLoanSimpleReceiverBase.sol";
import "@aave/v3-core/contracts/interfaces/IPoolAddressesProvider.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title FlashArbitrage
 * @notice Atomic flash loan arbitrage execution contract for Polygon
 * @dev Executes arbitrage trades atomically using Aave V3 flash loans
 * 
 * SECURITY FEATURES:
 * - Owner-only execution
 * - Profit validation before repayment
 * - Reentrancy protection
 * - Emergency withdrawal functions
 * 
 * SUPPORTED OPERATIONS:
 * 1. Direct arbitrage (buy on DEX A, sell on DEX B)
 * 2. Triangular arbitrage (A -> B -> C -> A)
 * 3. Multi-hop swaps with flash loans
 */
contract FlashArbitrage is FlashLoanSimpleReceiverBase, Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // =============================================================================
    // STRUCTS
    // =============================================================================
    
    struct SwapParams {
        address router;      // DEX router address
        address[] path;      // Swap path
        uint256 amountIn;    // Amount to swap
        uint256 minAmountOut; // Minimum acceptable output
        uint256 deadline;    // Transaction deadline
    }

    struct ArbitrageParams {
        SwapParams[] swaps;           // Array of swaps to execute
        uint256 minProfit;            // Minimum profit required (in loan token)
        address profitToken;          // Token to measure profit in
    }

    // =============================================================================
    // EVENTS
    // =============================================================================
    
    event ArbitrageExecuted(
        address indexed token,
        uint256 loanAmount,
        uint256 profit,
        uint256 gasUsed
    );
    
    event SwapExecuted(
        address indexed router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 amountOut
    );
    
    event EmergencyWithdraw(
        address indexed token,
        uint256 amount
    );

    // =============================================================================
    // STATE VARIABLES
    // =============================================================================
    
    // Approved DEX routers (for security)
    mapping(address => bool) public approvedRouters;
    
    // Statistics
    uint256 public totalArbitrages;
    uint256 public totalProfit;
    
    // Gas tracking
    uint256 private _gasStart;

    // =============================================================================
    // CONSTRUCTOR
    // =============================================================================
    
    constructor(
        address _addressProvider
    ) FlashLoanSimpleReceiverBase(IPoolAddressesProvider(_addressProvider)) Ownable(msg.sender) {
        // Pre-approve common Polygon DEX routers
        
        // QuickSwap V2
        approvedRouters[0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff] = true;
        
        // SushiSwap
        approvedRouters[0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506] = true;
        
        // ApeSwap
        approvedRouters[0xC0788A3aD43d79aa53B09c2EaCc313A787d1d607] = true;
        
        // DFYN
        approvedRouters[0xA102072A4C07F06EC3B4900FDC4C7B80b6c57429] = true;
        
        // MeshSwap
        approvedRouters[0x10f4A785F458Bc144e3706575924889954946639] = true;
    }

    // =============================================================================
    // ADMIN FUNCTIONS
    // =============================================================================
    
    /**
     * @notice Add or remove approved router
     */
    function setRouterApproval(address router, bool approved) external onlyOwner {
        approvedRouters[router] = approved;
    }
    
    /**
     * @notice Emergency withdraw stuck tokens
     */
    function emergencyWithdraw(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        if (balance > 0) {
            IERC20(token).safeTransfer(owner(), balance);
            emit EmergencyWithdraw(token, balance);
        }
    }
    
    /**
     * @notice Emergency withdraw ETH/MATIC
     */
    function emergencyWithdrawETH() external onlyOwner {
        uint256 balance = address(this).balance;
        if (balance > 0) {
            payable(owner()).transfer(balance);
        }
    }

    // =============================================================================
    // FLASH LOAN EXECUTION
    // =============================================================================
    
    /**
     * @notice Execute arbitrage with flash loan
     * @param asset Token to borrow
     * @param amount Amount to borrow
     * @param params Encoded ArbitrageParams
     */
    function executeArbitrage(
        address asset,
        uint256 amount,
        bytes calldata params
    ) external onlyOwner nonReentrant {
        _gasStart = gasleft();
        
        // Request flash loan from Aave
        POOL.flashLoanSimple(
            address(this),
            asset,
            amount,
            params,
            0 // referralCode
        );
    }

    /**
     * @notice Aave flash loan callback
     * @dev This is called by Aave after we receive the loan
     */
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        // Security: Only Aave pool can call this
        require(msg.sender == address(POOL), "Caller must be Aave Pool");
        require(initiator == address(this), "Initiator must be this contract");
        
        // Decode arbitrage parameters
        ArbitrageParams memory arbParams = abi.decode(params, (ArbitrageParams));
        
        // Record starting balance
        uint256 startBalance = IERC20(asset).balanceOf(address(this));
        
        // Execute all swaps
        for (uint256 i = 0; i < arbParams.swaps.length; i++) {
            _executeSwap(arbParams.swaps[i]);
        }
        
        // Calculate profit
        uint256 endBalance = IERC20(asset).balanceOf(address(this));
        uint256 totalOwed = amount + premium;
        
        // Verify profitability
        require(endBalance >= totalOwed + arbParams.minProfit, "Insufficient profit");
        
        uint256 profit = endBalance - totalOwed;
        
        // Approve repayment
        IERC20(asset).safeApprove(address(POOL), totalOwed);
        
        // Update statistics
        totalArbitrages++;
        totalProfit += profit;
        
        // Transfer profit to owner
        if (profit > 0) {
            IERC20(asset).safeTransfer(owner(), profit);
        }
        
        uint256 gasUsed = _gasStart - gasleft();
        emit ArbitrageExecuted(asset, amount, profit, gasUsed);
        
        return true;
    }

    // =============================================================================
    // SWAP EXECUTION
    // =============================================================================
    
    /**
     * @notice Execute a single swap on a DEX
     */
    function _executeSwap(SwapParams memory swap) internal {
        require(approvedRouters[swap.router], "Router not approved");
        require(swap.path.length >= 2, "Invalid path");
        require(swap.deadline >= block.timestamp, "Deadline expired");
        
        address tokenIn = swap.path[0];
        address tokenOut = swap.path[swap.path.length - 1];
        
        // Approve router to spend tokens
        IERC20(tokenIn).safeApprove(swap.router, swap.amountIn);
        
        // Execute swap using Uniswap V2 interface (common across DEXs)
        uint256 balanceBefore = IERC20(tokenOut).balanceOf(address(this));
        
        IUniswapV2Router(swap.router).swapExactTokensForTokens(
            swap.amountIn,
            swap.minAmountOut,
            swap.path,
            address(this),
            swap.deadline
        );
        
        uint256 balanceAfter = IERC20(tokenOut).balanceOf(address(this));
        uint256 amountOut = balanceAfter - balanceBefore;
        
        emit SwapExecuted(swap.router, tokenIn, tokenOut, swap.amountIn, amountOut);
    }

    // =============================================================================
    // VIEW FUNCTIONS
    // =============================================================================
    
    /**
     * @notice Simulate arbitrage without execution
     * @dev Uses staticcall to estimate outcomes
     */
    function simulateArbitrage(
        address asset,
        uint256 amount,
        ArbitrageParams calldata params
    ) external view returns (uint256 estimatedProfit, bool wouldSucceed) {
        // This is a simplified simulation
        // In production, use more sophisticated modeling
        
        uint256 premium = (amount * 5) / 10000; // 0.05% flash loan fee
        uint256 totalOwed = amount + premium;
        
        // Estimate total output from swaps
        uint256 estimatedOutput = amount;
        
        for (uint256 i = 0; i < params.swaps.length; i++) {
            // Rough estimate: assume 0.3% fee per swap
            estimatedOutput = (estimatedOutput * 997) / 1000;
        }
        
        if (estimatedOutput > totalOwed) {
            estimatedProfit = estimatedOutput - totalOwed;
            wouldSucceed = estimatedProfit >= params.minProfit;
        } else {
            estimatedProfit = 0;
            wouldSucceed = false;
        }
    }

    /**
     * @notice Get contract statistics
     */
    function getStats() external view returns (
        uint256 _totalArbitrages,
        uint256 _totalProfit,
        uint256 _contractBalance
    ) {
        return (
            totalArbitrages,
            totalProfit,
            address(this).balance
        );
    }

    // =============================================================================
    // RECEIVE FUNCTION
    // =============================================================================
    
    receive() external payable {}
}

// =============================================================================
// INTERFACES
// =============================================================================

interface IUniswapV2Router {
    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);
    
    function getAmountsOut(
        uint256 amountIn,
        address[] calldata path
    ) external view returns (uint256[] memory amounts);
}
