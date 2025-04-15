import smartpy as sp
import smartpy.utils as utils

# Define addresses

# The address which acts as the Governor
GOVERNOR_ADDRESS = sp.address("tz1YYnf7vGXqCmB1shNg4rHiTz5gwWTDYceB")

# The address which acts as the addLiquidity Executor
EXECUTOR_ADDRESS = sp.address("tz1YYnf7vGXqCmB1shNg4rHiTz5gwWTDYceB")

# The address that acts as the token contract.
TOKEN_ADDRESS = sp.address("KT1RBR9i6R7T56DJbaUtzDNuCt9KHLM8bVpW")

# The address of a XTZ/kUSD Quipuswap contract
QUIPUSWAP_ADDRESS = sp.address("KT1VVYfncoCWrwG6Bwd4MFuq3Xj8c4ndW5qF")

# The address of the Youves Spot Price (views)
YOUVES_SPOT_ADDRESS = sp.address("KT1UcwQtaztLSq8oufdXAtWpRTfFySCj7gFM")

# An address which is never used. This is a `null` value for addresses.
NULL_ADDRESS = sp.address("tz1bTpviNnyx2PXsNmGpCQTMQsGoYordkUoA")

# An address which can be rotated.
ROTATED_ADDRESS = sp.address("tz1UMCB2AHSTwG7YcGNr31CqYCtGN873royv")

# An address which acts as a Liquidity Fund
LIQUIDITY_FUND_ADDRESS = sp.address("tz1R6Ej25VSerE3MkSoEEeBjKHCDTFbpKuSX")

# An address which acts as a pause guardian
PAUSE_GUARDIAN_ADDRESS = sp.address("tz1YYnf7vGXqCmB1shNg4rHiTz5gwWTDYceB")

# An address which will receive the swapped tokens
RECEIVER_ADDRESS = sp.address("tz1YYnf7vGXqCmB1shNg4rHiTz5gwWTDYceB")

# An address of a Baker
BAKER_PUBLIC_KEY_HASH = "tz3RDC3Jdn4j15J7bBHZd29EUee9gVB1CxD9"
BAKER_ADDRESS = sp.address(BAKER_PUBLIC_KEY_HASH)
BAKER_KEY_HASH = sp.key_hash(BAKER_PUBLIC_KEY_HASH)
VOTING_POWERS = {
    BAKER_KEY_HASH: 8000,
}

# An series of named addresses with no particular role.
# These are used for token transfer tests.
ALICE_ADDRESS = sp.address("tz1VQnqCCqX4K5sP3FNkVSNKTdCAMJDd3E1n")
BOB_ADDRESS = sp.address("tz2FCNBrERXtaTtNX6iimR1UJ5JSDxvdHM93")
CHARLIE_ADDRESS = sp.address("tz3S6BBeKgJGXxvLyZ1xzXzMPn11nnFtq5L9")

# from test_helpers.addresses import addresses as Addresses
# from common.constants import constants as Constants
# from common.errors import errors as Errors


################################################################
# Constants
################################################################


@sp.module
def Constants():
    # The fixed point number representing 1 in the system, 10^18
    PRECISION = sp.nat(1000000000000000000)

    # The XTZUSDT asset pair reported by Youves.
    XTZ_ASSET_CODE = "XTZUSDT"

    # The USDTUSD asset pair reported by Youves.
    USDT_ASSET_CODE = "USDTUSD"


################################################################
# Errors
################################################################


@sp.module
def Errors():
    # The sender of a contract invocation was required to be the Governor contract.
    NOT_GOVERNOR = 1

    # The sender of an operation was required to be the Administrator of the contract.
    NOT_EXECUTOR = 2

    # The sender of an operation was required to be the Pause Guardian.
    NOT_PAUSE_GUARDIAN = 3

    # The data provided was too old.
    STALE_DATA = 4

    # The system is paused.
    PAUSED = 5

    # Cannot receive funds.
    CANNOT_RECEIVE_FUNDS = 6

    # The swap was attempted before min delay time
    TRADE_TIME = 7

    # USDT does not equal USD
    USDT_PEG = 8

    # Not enough tokens to perform swap
    NOT_ENOUGH_TOKENS = 9

    # The sender was not the expected contract
    BAD_SENDER = 10

    # Error calling view on Youves spot
    SPOT_VIEW_ERROR = 12

    # Error while interacting with DEX contract
    DEX_CONTRACT_ERROR = 13

    # Wrong state while interacting with function
    BAD_STATE = 14

    # Error while calling approve on token
    APPROVAL = 15

    # Error while executing the transfer function in token
    TOKEN_TRANSFER = 17

    # Error while retrieving balance of token
    BALANCE_REQUEST = 18

    ## BELOW ARE ONLY USED IN TESTS ##
    # The user did not have a sufficient token balance to complete the operation.
    TOKEN_INSUFFICIENT_BALANCE = 19

    # The allowance change was unsafe. Please reset the allowance to zero before trying to operation again.
    TOKEN_UNSAFE_ALLOWANCE_CHANGE = 20

    # The operation was not performed by the token administrator.
    TOKEN_NOT_ADMINISTRATOR = 21

    # The debt ceiling would be exceeded if the operation were completed.
    DEBT_CEILING = 22

    # The user was not allowed to perform a token transfer.
    TOKEN_NO_TRANSFER_PERMISSION = 23

    # The sender of an operation was required to be Executor or Governor
    NOT_AUTHORIZED = 24


################################################################
# Contract
################################################################


@sp.module
def quipu():
    import Constants
    import Errors
    import smartpy.utils as utils

    # State Machine
    IDLE = 0
    WAITING_FOR_TOKEN_BALANCE = 1

    class MakerContract(sp.Contract):
        def __init__(
            self,
            governorContractAddress,
            pauseGuardianContractAddress,
            receiverContractAddress,
            spotContractAddress,
            quipuswapContractAddress,
            tokenAddress,
            paused,
            maxDataDelaySec,  # 5 minutes
            minTradeDelaySec,  # Time to wait in seconds between allowing swaps (use 0 to allow batch transactions)
            spreadAmount,  # How far below the oracle price the exchange price must be in percent before allowing a swap. Scale 1-1000, 10=1%
            tradeAmount,
            tokenBalance,  # this should be 0 when deployed
            lastTradeTime,
            state,
        ):
            self.data.governorContractAddress = governorContractAddress
            self.data.pauseGuardianContractAddress = pauseGuardianContractAddress
            self.data.receiverContractAddress = receiverContractAddress
            self.data.spotContractAddress = spotContractAddress
            self.data.quipuswapContractAddress = quipuswapContractAddress
            self.data.tokenAddress = tokenAddress
            self.data.paused = paused
            self.data.maxDataDelaySec = maxDataDelaySec
            self.data.minTradeDelaySec = minTradeDelaySec
            self.data.spreadAmount = spreadAmount
            self.data.tradeAmount = tradeAmount
            self.data.tokenBalance = tokenBalance
            self.data.lastTradeTime = lastTradeTime
            self.data.state = state

        ################################################################
        # Quipuswap API
        ################################################################

        @sp.entrypoint
        def tokenToTezPayment(self):
            # Verify the contract isn't paused.
            assert sp.amount == sp.tez(0)
            assert not self.data.paused, Errors.PAUSED

            # Make sure enough time has passed
            timeDeltaSeconds = sp.as_nat(sp.now - self.data.lastTradeTime)
            assert timeDeltaSeconds >= self.data.minTradeDelaySec, Errors.TRADE_TIME

            # Tether depeg protection
            # Read USDUSDT price from Youves
            youvesUsdt = sp.view(
                "get_price_with_timestamp",
                self.data.spotContractAddress,
                Constants.USDT_ASSET_CODE,
                sp.pair[
                    sp.nat, # Price
                    sp.timestamp,  # Time
                ]
            ).unwrap_some(error=Errors.SPOT_VIEW_ERROR)

            # Extract USDT price
            usdtPrice = sp.fst(youvesUsdt)

            # Assert that USDT price is at least 99% of USD price
            assert usdtPrice >= 990000, Errors.USDT_PEG

            # Read spot price from Youves Spot
            youvesSpot = sp.view(
                "get_price_with_timestamp",
                self.data.spotContractAddress,
                Constants.XTZ_ASSET_CODE,
                sp.pair[
                    sp.nat, # Price
                    sp.timestamp,  # Time
                ]
            ).unwrap_some(error=Errors.SPOT_VIEW_ERROR)

            # Extract spot price
            spotPrice = sp.fst(youvesSpot)
            
            # Assert that the Youves spot data is newer than max data delay
            spotAge = utils.seconds_of_timestamp(sp.snd(youvesSpot)) / 1000 # Convert this timestamp from milliseconds to seconds
            dataAge = utils.seconds_of_timestamp(sp.now) - spotAge
            assert sp.as_nat(dataAge) <= self.data.maxDataDelaySec, Errors.STALE_DATA

            # Upsample
            tokensToTrade = self.data.tradeAmount * Constants.PRECISION

            # Calculate the expected XTZ with no slippage.
            # Expected out with no slippage = (number of tokens to trade / mutez Spot price) / 1e6
            neutralOut = (tokensToTrade / spotPrice) / 1_000_000
            
            # Apply spread multiplier
            # Expected out multiplied by spread = (neutral out from above) * (1 + spread amount)
            percent = sp.nat(1000) + self.data.spreadAmount
            requiredOut = (
                neutralOut * percent
            ) / 1000  # Note that percent is specified in scale = 1000
            
            # Approve Quipuswap contract to spend on token contract
            approveHandle = sp.contract(
                sp.pair[sp.address, sp.nat], self.data.tokenAddress, "approve"
            ).unwrap_some(error=Errors.APPROVAL)
            approveArg = (self.data.quipuswapContractAddress, tokensToTrade)
            sp.transfer(approveArg, sp.mutez(0), approveHandle)

            # Invoke a quipuswap trade
            tradeHandle = sp.contract(
                sp.pair[sp.pair[sp.nat, sp.nat], sp.address],
                self.data.quipuswapContractAddress,
                "tokenToTezPayment",
            ).unwrap_some(error=Errors.DEX_CONTRACT_ERROR)
            tradeArg = ((tokensToTrade, requiredOut), self.data.receiverContractAddress)
            sp.transfer(tradeArg, sp.mutez(0), tradeHandle)

            # Write last trade timestamp to storage
            self.data.lastTradeTime = sp.now

            # Revoke Quipuswap contract approval on token contract
            approveHandle = sp.contract(
                sp.pair[sp.address, sp.nat], self.data.tokenAddress, "approve"
            ).unwrap_some(error=Errors.APPROVAL)
            approveArg = (self.data.quipuswapContractAddress, 0)
            sp.transfer(approveArg, sp.mutez(0), approveHandle)
            


        ################################################################
        #  Balance functions
        ################################################################

        # Return FA 1.2 balance to receiverContractAddress
        @sp.entrypoint
        def returnBalance(self):
            assert sp.amount == sp.tez(0)
            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR

            # Verify state is correct.
            assert self.data.state == IDLE, Errors.BAD_STATE

            # Call token contract to update balance.
            param = (
                sp.self_address(),
                sp.self_entrypoint("redeemCallback"),
            )
            contractHandle = sp.contract(
                sp.pair[sp.address, sp.contract[sp.nat]],
                self.data.tokenAddress,
                "getBalance",
            ).unwrap_some()
            sp.transfer(param, sp.mutez(0), contractHandle)

            # Save state to state machine
            self.data.state = WAITING_FOR_TOKEN_BALANCE

        # Private callback for updating Balance.
        @sp.entrypoint
        def redeemCallback(self, updatedBalance):
            assert sp.amount == sp.tez(0)
            updatedBalance = sp.cast(updatedBalance, sp.nat)

            # Validate sender
            assert sp.sender == self.data.tokenAddress, Errors.BAD_SENDER

            # Verify state is correct.
            assert self.data.state == WAITING_FOR_TOKEN_BALANCE, Errors.BAD_STATE

            self.data.tokenBalance = updatedBalance

            # Send balance to Receiver
            sendParam = (
                sp.self_address(),
                self.data.receiverContractAddress,
                self.data.tokenBalance,
            )

            sendHandle = sp.contract(
                sp.tuple[sp.address, sp.address, sp.nat],
                self.data.tokenAddress,
                "transfer",
            ).unwrap_some()
            sp.transfer(sendParam, sp.mutez(0), sendHandle)

            # Reset state
            self.data.state = IDLE

        ################################################################
        # Pause Guardian
        ################################################################

        # Pause the system
        @sp.entrypoint
        def pause(self):
            assert sp.amount == sp.tez(0)
            assert (
                sp.sender == self.data.pauseGuardianContractAddress
            ), Errors.NOT_PAUSE_GUARDIAN
            self.data.paused = True

        ################################################################
        # Governance
        ################################################################

        # Update the max data delay (stale data).
        @sp.entrypoint
        def setMaxDataDelaySec(self, newMaxDataDelaySec):
            assert sp.amount == sp.tez(0)
            newMaxDataDelaySec = sp.cast(newMaxDataDelaySec, sp.nat)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.maxDataDelaySec = newMaxDataDelaySec

        # Update the delay between swaps.
        @sp.entrypoint
        def setMinTradeDelaySec(self, newMinTradeDelaySec):
            assert sp.amount == sp.tez(0)
            newMinTradeDelaySec = sp.cast(newMinTradeDelaySec, sp.nat)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.minTradeDelaySec = newMinTradeDelaySec

        # Set the trade amount (in normalized tokens).
        @sp.entrypoint
        def setTradeAmount(self, newTradeAmount):
            assert sp.amount == sp.tez(0)
            newTradeAmount = sp.cast(newTradeAmount, sp.nat)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.tradeAmount = newTradeAmount

        # Set spread amount (in percent)
        @sp.entrypoint
        def setSpreadAmount(self, newSpreadAmount):
            assert sp.amount == sp.tez(0)
            newSpreadAmount = sp.cast(newSpreadAmount, sp.nat)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.spreadAmount = newSpreadAmount

        # Unpause the system.
        @sp.entrypoint
        def unpause(self):
            assert sp.amount == sp.tez(0)
            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.paused = False

        # Update the Youves spot contract.
        @sp.entrypoint
        def setSpotContract(self, newSpotContractAddress):
            assert sp.amount == sp.tez(0)
            newSpotContractAddress = sp.cast(newSpotContractAddress, sp.address)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.spotContractAddress = newSpotContractAddress

        # Update the FA 1.2 token contract.
        @sp.entrypoint
        def setTokenContract(self, newTokenContractAddress):
            assert sp.amount == sp.tez(0)
            newTokenContractAddress = sp.cast(newTokenContractAddress, sp.address)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.tokenAddress = newTokenContractAddress

        # Update the pause guardian contract.
        @sp.entrypoint
        def setPauseGuardianContract(self, newPauseGuardianContractAddress):
            assert sp.amount == sp.tez(0)
            newPauseGuardianContractAddress = sp.cast(
                newPauseGuardianContractAddress, sp.address
            )

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.pauseGuardianContractAddress = newPauseGuardianContractAddress

        # Update the Quipuswap AMM contract.
        @sp.entrypoint
        def setQuipuswapContract(self, newQuipuswapContractAddress):
            assert sp.amount == sp.tez(0)
            newQuipuswapContractAddress = sp.cast(
                newQuipuswapContractAddress, sp.address
            )

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.quipuswapContractAddress = newQuipuswapContractAddress

        # Update the governor contract.
        @sp.entrypoint
        def setGovernorContract(self, newGovernorContractAddress):
            assert sp.amount == sp.tez(0)
            newGovernorContractAddress = sp.cast(newGovernorContractAddress, sp.address)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.governorContractAddress = newGovernorContractAddress

        # Update the Receiver contract.
        @sp.entrypoint
        def setReceiverContract(self, newReceiverContractAddress):
            assert sp.amount == sp.tez(0)
            newReceiverContractAddress = sp.cast(newReceiverContractAddress, sp.address)

            assert sp.sender == self.data.governorContractAddress, Errors.NOT_GOVERNOR
            self.data.receiverContractAddress = newReceiverContractAddress
			
# # Only run tests if this file is main.
# if __name__ == "__main__":

#   ################################################################
#   ################################################################
#   # Tests
#   ################################################################
#   ################################################################
  
#   FakeHarbingerVwap = sp.io.import_script_from_url("file:test-helpers/fake-harbinger-normalizer.py")
#   FakeHarbingerSpot = sp.import_script_from_url("file:test-helpers/fake-harbinger-spot.py")
#   FakeQuipuswap = sp.io.import_script_from_url("file:test-helpers/fake-quipuswap.py")


#   ################################################################
#   # tokenToTezPayment
#   ################################################################


#   @sp.add_test(name="tokenToTezPayment - correctly calculates amount out with 10 percent spread")
#   def test():
#     scenario = sp.test_scenario()
    
#     # GIVEN a moment in time.
#     currentTime = sp.timestamp(1000)
    
    
#     # AND fake harbinger normalizer contract
#     harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
#       harbingerValue = sp.nat(1_000_000), # $1.00
#       harbingerUpdateTime = currentTime,
#       harbingerAsset = Constants.ASSET_CODE
#     )
#     scenario += harbingerVwap
    
#     # AND fake harbinger spot contract
#     harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
#       harbingerValue = sp.nat(1_000_000), # $1.00
#       harbingerUpdateTime = currentTime,
#       harbingerAsset = Constants.ASSET_CODE,
#       harbingerVolume = sp.nat(1000)
#     )
#     scenario += harbingerSpot

#     # AND a fake quipuswap contract
#     quipuswap = FakeQuipuswap.FakeQuipuswapContract()
#     scenario += quipuswap
    
#     # AND a Market Making Ceiling contract with 10% spread requirement
#     maxDataDelaySec = 60
#     minTradeDelaySec = 1
#     lastTrade = sp.timestamp(1)
#     proxy = MakerContract(
#       vwapContractAddress = harbingerVwap.address,
#       spotContractAddress = harbingerSpot.address,
#       quipuswapContractAddress = quipuswap.address,
#       maxDataDelaySec = maxDataDelaySec,
#       minTradeDelaySec = minTradeDelaySec,
#       lastTradeTime = lastTrade,
#       spreadAmount = sp.nat(10),
#     )
#     scenario += proxy

#     # WHEN a trade is initiated
#     param = (sp.nat(10), sp.nat(1), Addresses.RECEIVER_ADDRESS)
#     amount = sp.nat(10)
#     scenario += proxy.tokenToTezPayment().run(
#       now = currentTime
#     )

#     # THEN a trade was attempted requiring a 10% spread between harbinger price and quipuswap price
#     # Expected Amount = (tokens sent / harbinger price) * (1 + (spread amount // 100))
#     #                 = (10 / $1.00) * (1 + .1)
#     #                 = 10 * 1.1
#     #                 = 11
#     scenario.verify(quipuswap.data.amountOut == 11 * 1_000_000)
#     scenario.verify(quipuswap.data.destination == Addresses.RECEIVER_ADDRESS)

#   @sp.add_test(name="tokenToTezPayment - correctly calculates amount out with no spread")
#   def test():
#     scenario = sp.test_scenario()
    
#     # GIVEN a moment in time.
#     currentTime = sp.timestamp(1000)
    
#     # AND fake harbinger normalizer contract
#     harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
#       harbingerValue = sp.nat(1_000_000), # $1.00
#       harbingerUpdateTime = currentTime,
#       harbingerAsset = Constants.ASSET_CODE
#     )
#     scenario += harbingerVwap
    
#     # AND fake harbinger spot contract
#     harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
#       harbingerValue = sp.nat(1_000_000), # $1.00
#       harbingerUpdateTime = currentTime,
#       harbingerAsset = Constants.ASSET_CODE,
#       harbingerVolume = sp.nat(1000)
#     )
#     scenario += harbingerSpot

#     # AND a fake quipuswap contract
#     quipuswap = FakeQuipuswap.FakeQuipuswapContract()
#     scenario += quipuswap
    
#     # AND a Market Making Ceiling contract with 0% spread requirement
#     spreadAmount = 0
#     maxDataDelaySec = 60
#     minTradeDelaySec = 1
#     lastTrade = sp.timestamp(1)
#     proxy = MakerContract(
#       vwapContractAddress = harbingerVwap.address,
#       spotContractAddress = harbingerSpot.address,
#       quipuswapContractAddress = quipuswap.address,
#       maxDataDelaySec = maxDataDelaySec,
#       minTradeDelaySec = minTradeDelaySec,
#       lastTradeTime = lastTrade,
#       spreadAmount = spreadAmount,
#     )
#     scenario += proxy

#     # WHEN a trade is initiated
#     scenario += proxy.tokenToTezPayment().run(
#       now = currentTime
#     )

#     # THEN a trade was attempted requiring a 0 spread between harbinger price and quipuswap price
#     # Expected Amount = (tokens sent / harbinger price) * (1 + (spread amount / 100))
#     #                 = (10 / $1.00) * (1 + 0)
#     #                 = 10 * 1
#     #                 = 10
#     scenario.verify(quipuswap.data.amountOut == 10 * 1_000_000)
#     scenario.verify(quipuswap.data.destination == Addresses.RECEIVER_ADDRESS)

#   @sp.add_test(name="tokenToTezPayment - fails if oracle is outdated")
#   def test():
#     scenario = sp.test_scenario()
    
#     # GIVEN a moment in time.
#     currentTime = sp.timestamp(1000)

#     # AND fake harbinger normalizer
#     harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
#       harbingerValue = sp.nat(3_500_000),
#       harbingerAsset = Constants.ASSET_CODE
#     )
#     scenario += harbingerVwap

#     # AND fake harbinger spot contract that is out of date
#     lastUpdateTime = sp.timestamp(500)
#     harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
#       harbingerValue = sp.nat(3_500_000), # $3.50
#       harbingerUpdateTime = lastUpdateTime,
#       harbingerAsset = Constants.ASSET_CODE
#     )
#     scenario += harbingerSpot
    
#     # AND a Quipuswap Proxy contract with max data delay less than (currentTime - lastUpdateTime)
#     maxDataDelaySec = sp.nat(499) # currentTime - lastUpdateTime - 1
#     proxy = MakerContract(
#       spotContractAddress = harbingerSpot.address,
#       vwapContractAddress = harbingerVwap.address,
#       maxDataDelaySec = maxDataDelaySec
#     )
#     scenario += proxy

#     # WHEN a trade is initiated
#     # THEN the call fails
#     scenario += proxy.tokenToTezPayment().run(
#       sender = Addresses.NULL_ADDRESS,
#       now = currentTime,
#       valid = False,
#       exception = Errors.STALE_DATA
#     )

#   @sp.add_test(name="tokenToTezPayment - fails if contract is paused")
#   def test():
#     # GIVEN a Quipuswap Proxy contract that is paused
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       paused = True
#     )
#     scenario += proxy

#     # WHEN a trade is initiated
#     # THEN the call fails
#     scenario += proxy.tokenToTezPayment().run(
#       valid = False,
#       exception = Errors.PAUSED
#     )

#   @sp.add_test(name="tokenToTezPayment - fails if trade is sooner than minimum delay")
#   def test():
#     # GIVEN a Quipuswap Proxy contract with minimum trade delay of 60 seconds
#     scenario = sp.test_scenario()

#     delay = 60
#     proxy = MakerContract(
#       minTradeDelaySec = delay
#     )
#     scenario += proxy

#     # WHEN a trade is initiated at a time sooner than the minimum trade delay
#     # THEN the call fails
#     stamp = sp.timestamp(delay - 1)

#     scenario += proxy.tokenToTezPayment().run(
#       now = stamp,
#       valid = False,
#       exception = Errors.TRADE_TIME
#     )

#   @sp.add_test(name="tokenToTezPayment - fails if volatility between VWAP and Spot is too great")
#   def test():
#     scenario = sp.test_scenario()

#     # GIVEN a moment in time.
#     currentTime = sp.timestamp(1000)
    
#     # AND fake harbinger normalizer contract with a price of $1.00
#     harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
#       harbingerValue = sp.nat(1_000_000), # $1.00
#       harbingerUpdateTime = currentTime,
#       harbingerAsset = Constants.ASSET_CODE
#     )
#     scenario += harbingerVwap
    
#     # AND fake harbinger spot contract with a price of $1.10
#     harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
#       harbingerValue = sp.nat(1_100_000), # $1.10
#       harbingerUpdateTime = currentTime,
#       harbingerAsset = Constants.ASSET_CODE,
#       harbingerVolume = sp.nat(1000)
#     )
#     scenario += harbingerSpot

#     # AND Quipuswap Proxy contract with volatilityTolerance of 5%
#     proxy = MakerContract(
#       vwapContractAddress = harbingerVwap.address,
#       spotContractAddress = harbingerSpot.address,
#       volatilityTolerance = 5,
#     )
#     scenario += proxy

#     # WHEN a trade is initiated
#     # THEN the call fails
#     amount = sp.nat(10)
#     scenario += proxy.tokenToTezPayment().run(
#       now = currentTime,
#       valid = False,
#       exception = Errors.VOLATILITY
#     )

#   ################################################################
#   # returnBalance
#   ################################################################
#   @sp.add_test(name="returnBalance - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     # AND a market making contract
#     proxy = MakerContract()
#     scenario += proxy

#     # WHEN returnBalance is called by the governor THEN the call succeeds
#     scenario += proxy.returnBalance().run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#       valid = True
#     )

#   @sp.add_test(name="returnBalance - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     # AND a maker contract
#     proxy = MakerContract()
#     scenario += proxy

#     # WHEN returnBalance is called THEN the call fails
#     notGovernor = Addresses.NULL_ADDRESS
#     scenario += proxy.returnBalance().run(
#       sender = notGovernor,
#       valid = False
#     )

#   ################################################################
#   # pause
#   ################################################################

#   @sp.add_test(name="pause - succeeds when called by pause guardian")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       paused = False
#     )
#     scenario += proxy

#     # WHEN pause is called
#     scenario += proxy.pause().run(
#       sender = Addresses.PAUSE_GUARDIAN_ADDRESS,
#     )

#     # THEN the contract is paused
#     scenario.verify(proxy.data.paused == True)

#   @sp.add_test(name="pause - fails when not called by pause guardian")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       paused = False
#     )
#     scenario += proxy

#     # WHEN pause is called is called by someone who isn't the pause guardian THEN the call fails
#     scenario += proxy.pause().run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_PAUSE_GUARDIAN
#     )

#   ################################################################
#   # setMaxDataDelaySec
#   ################################################################

#   @sp.add_test(name="setMaxDataDelaySec - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       maxDataDelaySec = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setMaxDataDelaySec is called
#     newValue = sp.nat(20)
#     scenario += proxy.setMaxDataDelaySec(newValue).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the storage is updated
#     scenario.verify(proxy.data.maxDataDelaySec == newValue)

#   @sp.add_test(name="setMaxDataDelaySec - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       maxDataDelaySec = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setMaxDataDelaySec is called is called by someone who isn't the governor THEN the call fails
#     newValue = sp.nat(20)
#     scenario += proxy.setMaxDataDelaySec(newValue).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )

#   ################################################################
#   # setMinTradeDelaySec
#   ################################################################

#   @sp.add_test(name="setMinTradeDelaySec - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       minTradeDelaySec = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setMinTradeDelaySec is called
#     newValue = sp.nat(20)
#     scenario += proxy.setMinTradeDelaySec(newValue).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the storage is updated
#     scenario.verify(proxy.data.minTradeDelaySec == newValue)

#   @sp.add_test(name="setMinTradeDelaySec - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       maxDataDelaySec = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setMinTradeDelaySec is called is called by someone who isn't the governor THEN the call fails
#     newValue = sp.nat(20)
#     scenario += proxy.setMinTradeDelaySec(newValue).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )
    
#   ################################################################
#   # setSpreadAmount
#   ################################################################

#   @sp.add_test(name="setSpreadAmount - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       spreadAmount = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setSpreadAmount is called
#     newValue = sp.nat(20)
#     scenario += proxy.setSpreadAmount(newValue).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the storage is updated
#     scenario.verify(proxy.data.spreadAmount == newValue)

#   @sp.add_test(name="setSpreadAmount - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       spreadAmount = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setSpreadAmount is called is called by someone who isn't the governor THEN the call fails
#     newValue = sp.nat(20)
#     scenario += proxy.setSpreadAmount(newValue).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )

#   ################################################################
#   # setVolatilityTolerance
#   ################################################################

#   @sp.add_test(name="setVolatilityTolerance - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       volatilityTolerance = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setVolatilityTolerance is called
#     newValue = sp.nat(20)
#     scenario += proxy.setVolatilityTolerance(newValue).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the storage is updated
#     scenario.verify(proxy.data.volatilityTolerance == newValue)

#   @sp.add_test(name="setVolatilityTolerance - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       volatilityTolerance = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setVolatilityTolerance is called is called by someone who isn't the governor THEN the call fails
#     newValue = sp.nat(20)
#     scenario += proxy.setVolatilityTolerance(newValue).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )

#   ################################################################
#   # setTradeAmount
#   ################################################################

#   @sp.add_test(name="setTradeAmount - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       tradeAmount = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setTradeAmount is called
#     newValue = sp.nat(20)
#     scenario += proxy.setTradeAmount(newValue).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the storage is updated
#     scenario.verify(proxy.data.tradeAmount == newValue)

#   @sp.add_test(name="setTradeAmount - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       tradeAmount = sp.nat(10)
#     )
#     scenario += proxy

#     # WHEN setTradeAmount is called is called by someone who isn't the governor THEN the call fails
#     newValue = sp.nat(20)
#     scenario += proxy.setTradeAmount(newValue).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )

#   ################################################################
#   # unpause
#   ################################################################

#   @sp.add_test(name="unpause - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       paused = True
#     )
#     scenario += proxy

#     # WHEN unpause is called
#     scenario += proxy.unpause().run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the contract is unpaused
#     scenario.verify(proxy.data.paused == False)

#   @sp.add_test(name="unpause - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     proxy = MakerContract(
#       paused = True
#     )
#     scenario += proxy

#     # WHEN unpause is called is called by someone who isn't the governor THEN the call fails
#     scenario += proxy.unpause().run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )

#   ################################################################
#   # setSpotContract
#   ################################################################

#   @sp.add_test(name="setSpotContract - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     spotContractAddress = Addresses.HARBINGER_SPOT_ADDRESS
#     proxy = MakerContract(
#       spotContractAddress = spotContractAddress
#     )
#     scenario += proxy

#     # WHEN setSpotContract is called with a new contract
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setSpotContract(rotatedAddress).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the contract is updated.
#     scenario.verify(proxy.data.spotContractAddress == rotatedAddress)

#   @sp.add_test(name="setSpotContract - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     spotContractAddress = Addresses.HARBINGER_SPOT_ADDRESS
#     proxy = MakerContract(
#       spotContractAddress = spotContractAddress
#     )
#     scenario += proxy

#     # WHEN setSpotContract is called by someone who isn't the governor THEN the call fails
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setSpotContract(rotatedAddress).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )

#   ################################################################
#   # setVwapContract
#   ################################################################

#   @sp.add_test(name="setVwapContract - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     vwapContractAddress = Addresses.HARBINGER_VWAP_ADDRESS
#     proxy = MakerContract(
#       vwapContractAddress = vwapContractAddress
#     )
#     scenario += proxy

#     # WHEN setVwapContract is called with a new contract
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setVwapContract(rotatedAddress).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the contract is updated.
#     scenario.verify(proxy.data.vwapContractAddress == rotatedAddress)

#   @sp.add_test(name="setVwapContract - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     vwapContractAddress = Addresses.HARBINGER_VWAP_ADDRESS
#     proxy = MakerContract(
#       vwapContractAddress = vwapContractAddress
#     )
#     scenario += proxy

#     # WHEN setVwapContract is called by someone who isn't the governor THEN the call fails
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setVwapContract(rotatedAddress).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )

#   ################################################################
#   # setPauseGuardianContract
#   ################################################################

#   @sp.add_test(name="setPauseGuardianContract - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     pauseGuardianContractAddress = Addresses.PAUSE_GUARDIAN_ADDRESS
#     proxy = MakerContract(
#       pauseGuardianContractAddress = pauseGuardianContractAddress
#     )
#     scenario += proxy

#     # WHEN setPauseGuardianContract is called with a new contract
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setPauseGuardianContract(rotatedAddress).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the contract is updated.
#     scenario.verify(proxy.data.pauseGuardianContractAddress == rotatedAddress)

#   @sp.add_test(name="setPauseGuardianContract - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     pauseGuardianContractAddress = Addresses.PAUSE_GUARDIAN_ADDRESS
#     proxy = MakerContract(
#       pauseGuardianContractAddress = pauseGuardianContractAddress
#     )
#     scenario += proxy

#     # WHEN setPauseGuardianContract is called by someone who isn't the governor THEN the call fails
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setPauseGuardianContract(rotatedAddress).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     ) 

#   ################################################################
#   # setQuipuswapContract
#   ################################################################

#   @sp.add_test(name="setQuipuswapContract - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     quipuswapContractAddress = Addresses.QUIPUSWAP_ADDRESS
#     proxy = MakerContract(
#       quipuswapContractAddress = quipuswapContractAddress
#     )
#     scenario += proxy

#     # WHEN setQuipuswapContract is called with a new contract
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setQuipuswapContract(rotatedAddress).run(
#       sender = Addresses.GOVERNOR_ADDRESS,
#     )

#     # THEN the contract is updated.
#     scenario.verify(proxy.data.quipuswapContractAddress == rotatedAddress)

#   @sp.add_test(name="setQuipuswapContract - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     governorContractAddress = Addresses.GOVERNOR_ADDRESS
#     quipuswapContractAddress = Addresses.QUIPUSWAP_ADDRESS
#     proxy = MakerContract(
#       quipuswapContractAddress = quipuswapContractAddress
#     )
#     scenario += proxy

#     # WHEN setQuipuswapContract is called by someone who isn't the governor THEN the call fails
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setQuipuswapContract(rotatedAddress).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     ) 

#   ################################################################
#   # setGovernorContract
#   ################################################################

#   @sp.add_test(name="setGovernorContract - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     governorContractAddress = Addresses.GOVERNOR_ADDRESS
#     proxy = MakerContract(
#       governorContractAddress = governorContractAddress
#     )
#     scenario += proxy

#     # WHEN setGovernorContract is called with a new contract
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setGovernorContract(rotatedAddress).run(
#       sender = governorContractAddress,
#     )

#     # THEN the contract is updated.
#     scenario.verify(proxy.data.governorContractAddress == rotatedAddress)

#   @sp.add_test(name="setGovernorContract - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     governorContractAddress = Addresses.GOVERNOR_ADDRESS
#     proxy = MakerContract(
#       governorContractAddress = governorContractAddress
#     )
#     scenario += proxy

#     # WHEN setGovernorContract is called by someone who isn't the governor THEN the call fails
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setGovernorContract(rotatedAddress).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )    

#   ################################################################
#   # setReceiverContract
#   ################################################################

#   @sp.add_test(name="setReceiverContract - succeeds when called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     governorContractAddress = Addresses.GOVERNOR_ADDRESS
#     proxy = MakerContract(
#       governorContractAddress = governorContractAddress
#     )
#     scenario += proxy

#     # WHEN setReceiverContract is called with a new contract
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setReceiverContract(rotatedAddress).run(
#       sender = governorContractAddress,
#     )

#     # THEN the contract is updated.
#     scenario.verify(proxy.data.receiverContractAddress == rotatedAddress)

#   @sp.add_test(name="setReceiverContract - fails when not called by governor")
#   def test():
#     # GIVEN a Quipuswap Proxy contract
#     scenario = sp.test_scenario()

#     governorContractAddress = Addresses.GOVERNOR_ADDRESS
#     proxy = MakerContract(
#       governorContractAddress = governorContractAddress
#     )
#     scenario += proxy

#     # WHEN setReceiverContract is called by someone who isn't the governor THEN the call fails
#     rotatedAddress = Addresses.ROTATED_ADDRESS
#     scenario += proxy.setReceiverContract(rotatedAddress).run(
#       sender = Addresses.NULL_ADDRESS,
#       valid = False,
#       exception = Errors.NOT_GOVERNOR
#     )    

#   sp.add_compilation_target("quipu_swapper", MakerContract())
