### Quipuswap Maker Ceiling

## Overview

**USE THIS CONTRACT WITH CAUTION! THERE IS RISK WHEN SWAPPING TOKENS. IT IS UP TO THE USERS TO MANAGE THE RISK APPROPRIATELY. THIS CONTRACT DOES NOT ELIMINATE RISK, IT ONLY PROVIDES TOOLS FOR MANAGING RISK**

<br>

* **This contract acts as a market maker providing single-sided liquidity to the kUSD/XTZ Quipuswap pair**
* **The market making ceiling contract allows any party to invoke a function that will swap tokens in the contract for XTZ on behalf of the contract, as long as certain conditions are met**
* **The risk mitigation parameters can be understood as ways to make the execution fail. If the parameters are riskier, it will be easier to execute the swap. Conservative parameters make the swap more difficult to execute.**
* **Finding the right balance of parameters is important, and this balance will differ depending on the specific goals of the swap, along with external factors. It is recommended to start with conservative parameters**

## Risk Mitigation Parameters

`spreadAmount`: The amount in percent that the kUSD price on Quipuswap must be above the Harbinger Spot price before a swap will be allowed.

`volatilityTolerance`: The range in percent that the Harbinger Normalizer price must be relative to Harbinger Spot price (volatility between normalizer and spot)

`tradeAmount`: The amount of tokens to trade in each transaction, normalized.

`maxDataDelaySec`: The amount of time in seconds before Harbinger data is considered stale.

`minTradeDelaySec`: The amount of time in seconds that must pass before another swap is allowed.


## Example configurations
* **Bailout fund** - similar to Youves' bailout system, a high spread amount and trade delay of 0 allows batch swaps when someone needs to buy a lot of kUSD at a high premium.<br>
 `spreadAmount=15`, `volatilityTolerance=5`, `tradeAmount=1000`, `maxDataDelaySec=300`, `minTradeDelaySec=0`
* **Peg stability** - spread amount is set at a level outside of regular historical bounds, but low enough to provide liquidity at the extremes. A minimum trade delay equal to the maximum data delay ensures a new Harbinger update must be pushed before each trade.
 `spreadAmount=6`, `volatilityTolerance=3`, `tradeAmount=500`, `maxDataDelaySec=180`, `minTradeDelaySec=180`
* **Fire sale** - an example of trying to sell tokens very quickly, at a price at least equal to the Harbinger price. Note that as spread decreases we decrease the maximum data delay to offset some of the added risk. Since the objective is to fire sale, we allow batch swaps with a trade delay of 0.
 `spreadAmount=0`, `volatilityTolerance=3`, `tradeAmount=500`, `maxDataDelaySec=120`, `minTradeDelaySec=0`

## Attribution

This contract is based on [a contract by Hover Labs](https://github.com/Hover-Labs/kolibri-contracts/blob/keefertaylor/quipu-proxy/smart_contracts/quipuswap-proxy.py)
