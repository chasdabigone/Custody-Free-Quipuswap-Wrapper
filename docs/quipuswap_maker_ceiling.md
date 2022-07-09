# Quipuswap Maker Ceiling

## Overview

**USE THIS CONTRACT WITH CAUTION! THERE IS RISK WHEN SWAPPING TOKENS. IT IS UP TO THE USERS TO MANAGE THE RISK APPROPRIATELY. THIS CONTRACT DOES NOT ELIMINATE RISK, IT ONLY PROVIDES TOOLS FOR MANAGING RISK**

* **This MakerContract acts as a market maker providing single-sided liquidity to the kUSD/XTZ Quipuswap pair. It sells kUSD for XTZ**
* **The market making ceiling contract allows any party to invoke a function that will swap tokens in the contract for XTZ on behalf of the contract, as long as certain conditions are met**
* **The risk mitigation parameters can be understood as ways to make the execution fail. If the parameters are riskier, it will be easier to execute the swap. Conservative parameters make the swap more difficult to execute.**
* **Finding the right balance of parameters is important, and this balance will differ depending on the specific goals of the swap, along with external factors. It is recommended to start with a conservative configuration**

The governor can utilize all functions except for `pause` and `redeemCallback`. Anyone can execute the `tokenToTezPayment()` function which acts as a wrapper for the Quipuswap function of the same name.<br>
Governor should be a higher privileged multi-sig or DAO with a time lock.

## Risk Mitigation Parameters

`spreadAmount`: The amount in percent that the kUSD price on Quipuswap must be above the Harbinger Spot price before a swap will be allowed. This parameter has the most influence over whether a swap will be allowed. Low=Risky, High=Conservative<br>
`volatilityTolerance`: The range in percent that the Harbinger Normalizer price must be relative to Harbinger Spot price (volatility between normalizer and spot). This setting will make the swap fail during times of temporary volatility. Low=Conservative, High=Risky<br>
`tradeAmount`: The amount of tokens to trade in each transaction, normalized. Low=Conservative, High=Risky<br>
`maxDataDelaySec`: The amount of time in seconds before Harbinger data is considered stale. Low=Conservative, High=Risky<br>
`minTradeDelaySec`: The amount of time in seconds that must pass before another swap is allowed. Low=Risky, High=Conservative<br><br>
In addition, risk can be mitigated by only keeping a certain balance available in the contract at any one time.


## Example configurations
* **Bailout fund** - similar to Youves' bailout system, a high spread amount and trade delay of 0 allows batch swaps when someone needs to buy a lot of kUSD at a high premium.<br>
 `spreadAmount=15`, `volatilityTolerance=5`, `tradeAmount=2000`, `maxDataDelaySec=300`, `minTradeDelaySec=0`
* **Peg stability** - spread amount is set at a level outside of regular historical bounds, but low enough to provide liquidity at the extremes. A minimum trade delay equal to the maximum data delay ensures a new Harbinger update must be pushed before each trade.
 `spreadAmount=6`, `volatilityTolerance=3`, `tradeAmount=1000`, `maxDataDelaySec=180`, `minTradeDelaySec=180`
* **Fire sale** - an example of trying to sell tokens very quickly, at a price at least equal to the Harbinger price. Note that as spread decreases we decrease the maximum data delay to offset some of the added risk. Since the objective is to fire sale, we allow batch swaps with a trade delay of 0.
 `spreadAmount=0`, `volatilityTolerance=3`, `tradeAmount=500`, `maxDataDelaySec=120`, `minTradeDelaySec=0`
 
## Pros and cons vs OTC multisig swap
**Pros**: provide liquidity to those who need it most (those willing to pay more), eliminate custodial middleman (multisig), keep fees with Quipuswap LPers, provide confidence that liquidity will be available to pay loans during market downturns

**Cons**: Adds oracle risk, adds complexity, not guaranteed to swap

## Core Upgrade Path

Any contract which needs to interact with a MakerContract should have a governable reference to the MakerContract.

If a new MakerContract contract is needed then: (1) A new MakerContract contract would be deployed (2) The Governor would update every contract that interacts with the MakerContract to point to the new MakerContract. (3) The Governor would transfer existing tokens to the new MakerContract

## Storage
The MakerContract stores the following:<br>
`spreadAmount`(nat): The amount in percent that the kUSD price on Quipuswap must be above the Harbinger Spot price before a swap will be allowed.<br>
`volatilityTolerance`(nat): The range in percent that the Harbinger Normalizer price must be relative to Harbinger Spot price (volatility between normalizer and spot)<br>
`maxDataDelaySec`(nat): The amount of time in seconds before Harbinger data is considered stale.<br>
`minTradeDelaySec`(nat): The amount of time in seconds that must pass before another swap is allowed.<br>
`tradeAmount`(nat): The amount of tokens to trade in each transaction, normalized.<br>

`governorContractAddress` (address): The Governor<br>
`vwapContractAddress` (address): The address of the Harbinger Normalizer<br>
`spotContractAddress` (address): The address of the Harbinger Spot storage<br>
`pauseGuardianContractAddress` (address): The address of a pause guardian<br>
`quipuswapContractAddress` (address): The address of a Quipuswap AMM<br>
`receiverContractAddress` (address): The address that will receive the output XTZ from the Quipuswap AMM<br>
`tokenAddress` (address): The address of the FA1.2 token<br>
`lastTradeTime` (timestamp): The last time a trade was successfully executed.<br>
`paused` (bool): Whether the contract is paused or not.<br>
`tokenPrecision`(nat): The precision of the token. Only used in testing.<br>
`tokenBalance`(nat): The balance stored during balance request callback.<br>
`spotPrice`(nat): The spot price stored when `view`ing the Harbinger spot contract.<br>

## Entrypoints

The MakerContract has the following entrypoints:<br>
`pause`: Pauses the contract. Can only be called by the Pause Guardian<br>
`redeemCallback`: Private callback for FA1.2. Can only be called by the token contract.<br>
`returnBalance`: Send the FA1.2 token balance to the Receiver address. Can only be called by the Governor.<br>
`setGovernorContract`: set the governor contract address. Can only be called by the Governor.<br>
`setMaxDataDelaySec`: set the maximum data delay. Can only be called by the Governor.<br>
`setMinTradeDelaySec`: set the minimum time between trades. Can only be called by the Governor.<br>
`setPauseGuardianContract`: set the pause guardian address. Can only be called by the Governor.<br>
`setQuipuswapContract`: set the quipuswap AMM address. Can only be called by the Governor.<br>
`setReceiverContract`: set the receiver contract address. Can only be called by the Governor.<br>
`setSpotContract`: set the Harbinger Spot storage address. Can only be called by the Governor.<br>
`setSpreadAmount`: set the maximum spread amount with which a swap will be allowed. Can only be called by the Governor.<br>
`setTokenPrecision`: set the token precision. Can only be called by the Governor. Used for testing.<br>
`setTradeAmount`: set the trade amount per swap. Can only be called by the Governor.<br>
`setVolatilityTolerance`: set the tolerance in percent for volatility between Normalizer and Spot oracles. Can only be called by the Governor.<br>
`setVwapContract`: set the Harbinger Normalizer address. Can only be called by the Governor.<br>
`tokenToTezPayment`: attempt a swap on the Quipuswap AMM. Can be called by anyone.<br>
`unpause`: unpause the contract. Can only be called by the Governor.<br>

## Attribution

This contract is based on [a contract by Hover Labs](https://github.com/Hover-Labs/kolibri-contracts/blob/keefertaylor/quipu-proxy/smart_contracts/quipuswap-proxy.py)
