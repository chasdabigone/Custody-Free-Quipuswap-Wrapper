# Custody-free Quipuswap Wrapper

## What is this project?

* **This repo provides a way for Kolibri DAO to interact with Quipuswap on the Tezos blockchain without giving up custody of tokens or XTZ. It uses the Harbinger oracle to verify prices.**
* **`quipuswap_maker_ceiling.py` puts a price ceiling on a Quipuswap pair that allows anyone to invoke a swap on behalf of the contract when the price meets a set of defined parameters that interact with variable timestamp and price inputs from Harbinger.**
* **`quipuswap_liquidity_proxy.py` enables governance and liquidity functions. It uses Harbinger to verify that liquidity is not added at an unfavorable price.**
* **SWAPPING FUNDS IS INHERENTLY RISKY. DOING SO AUTONOMOUSLY ADDS EVEN MORE RISK. THIS REPO PROVIDES WAYS TO MANAGE THAT RISK. IT CANNOT AND DOES NOT PRETEND TO ELIMINATE THE RISK. USE WITH CAUTION**


## Instructions for use

This project was created using [SmartPy](https://smartpy.io) and requires the SmartPy CLI to interact

Set the addresses in `common/addresses.py`, compile, and deploy.

More detailed docs for each contract are available at:<br>
[Quipuswap Liquidity Proxy Documentation](https://github.com/chasdabigone/Custody-Free-Quipuswap-Wrapper/blob/main/docs/quipuswap_liquidity_proxy.md)<br>
[Quipuswap Maker Ceiling Documentation](https://github.com/chasdabigone/Custody-Free-Quipuswap-Wrapper/blob/main/docs/quipuswap_maker_ceiling.md)

## Licenses and attribution

This project is based on the work of [Hover Labs](https://hover.engineering). Specifically the [Kolibri Smart Contracts](https://github.com/Hover-Labs/kolibri-contracts/tree/master/smart_contracts).<br>

It is released under the MIT license.
                                                                                                                                                                                                                                                                                                                                                                                                                                    
## Contact information

For information or questions, message chas#7053 on Discord.
