import smartpy as sp

Addresses = sp.io.import_script_from_url("file:test-helpers/addresses.py")
Constants = sp.io.import_script_from_url("file:common/constants.py")
Errors = sp.io.import_script_from_url("file:common/errors.py")

################################################################
# Contract
################################################################

class MakerContract(sp.Contract):
  def __init__(
    self,

    governorContractAddress = Addresses.GOVERNOR_ADDRESS,
    pauseGuardianContractAddress = Addresses.PAUSE_GUARDIAN_ADDRESS,
    receiverContractAddress = Addresses.RECEIVER_ADDRESS, # Address to send the output to

    vwapContractAddress = Addresses.HARBINGER_VWAP_ADDRESS,
    spotContractAddress = Addresses.HARBINGER_SPOT_ADDRESS,
    quipuswapContractAddress = Addresses.QUIPUSWAP_ADDRESS,
    tokenAddress = Addresses.TOKEN_ADDRESS,

    paused = False,

    maxDataDelaySec = sp.nat(60 * 5), # 5 minutes
    minTradeDelaySec = sp.nat(0), # Time to wait in seconds between allowing swaps (use 0 to allow batch transactions)
    spreadAmount = sp.nat(0), # How far below the oracle price the exchange price must be in percent before allowing a swap
    volatilityTolerance = sp.nat(5), # 5%
    tradeAmount = sp.nat(10),

    tokenBalance = sp.nat(0), # this should be 0 when deployed
    lastTradeTime = sp.timestamp(1)

    
  ):
    self.init(
 
        governorContractAddress = governorContractAddress,
        pauseGuardianContractAddress = pauseGuardianContractAddress,
        receiverContractAddress = receiverContractAddress,

        vwapContractAddress = vwapContractAddress,
        spotContractAddress = spotContractAddress,
        quipuswapContractAddress = quipuswapContractAddress,      
        tokenAddress = tokenAddress,

        paused = paused,

        maxDataDelaySec = maxDataDelaySec,
        minTradeDelaySec = minTradeDelaySec,        
        spreadAmount = spreadAmount,      
        volatilityTolerance = volatilityTolerance,
        tradeAmount = tradeAmount,

        tokenBalance = tokenBalance,       
        lastTradeTime = lastTradeTime   
    )

  ################################################################
  # Quipuswap API
  ################################################################

  @sp.entry_point(check_no_incoming_transfer=True)
  def tokenToTezPayment(self):
    
    # Verify the contract isn't paused.
    sp.verify(self.data.paused == False, Errors.PAUSED)

    # Make sure enough time has passed
    timeDeltaSeconds = sp.as_nat(sp.now - self.data.lastTradeTime)
    sp.verify(timeDeltaSeconds >= self.data.minTradeDelaySec, Errors.TRADE_TIME)

    # Read vwap from Harbinger Normalizer
    harbingerVwap = sp.local('harbingerVwap', sp.view(
      "getPrice",
      self.data.vwapContractAddress,
      Constants.ASSET_CODE,
      sp.TPair(sp.TTimestamp, sp.TNat)
    ).open_some(message = Errors.VWAP_VIEW_ERROR))

    # Read spot price from Harbinger Spot
    harbingerSpot = sp.local('harbingerSpot', sp.view(
      "getPrice",
      self.data.spotContractAddress,
      Constants.ASSET_CODE,
      sp.TPair(
        sp.TTimestamp,                      # Start
        sp.TPair(
            sp.TTimestamp,                  # End
            sp.TPair(
                sp.TNat,                    # Open
                sp.TPair(
                    sp.TNat,                # High
                    sp.TPair(
                        sp.TNat,            # Low
                        sp.TPair(
                            sp.TNat,        # Close
                            sp.TNat         # Volume
                        )
                    )
                )
            )
        )
      )
    
    ).open_some(message = Errors.SPOT_VIEW_ERROR))

    # Extract spot price
    spotPrice = sp.local('spotPrice', (sp.fst(sp.snd(sp.snd(sp.snd(sp.snd(sp.snd(harbingerSpot.value))))))))

    # Assert that the Harbinger spot data is newer than max data delay
    dataAge = sp.as_nat(sp.now - sp.fst(sp.snd(harbingerSpot.value)))
    sp.verify(dataAge <= self.data.maxDataDelaySec, Errors.STALE_DATA)

    # Assert that latest Harbinger Normalizer update is newer than max data delay
    vwapAge = sp.as_nat(sp.now - sp.fst(harbingerVwap.value))
    sp.verify(vwapAge <= self.data.maxDataDelaySec, Errors.STALE_DATA)
  
    # Upsample price numbers using token precision constant
    harbingerVwapPrice = (sp.snd(harbingerVwap.value) * Constants.PRECISION) // 1_000_000
    harbingerSpotPrice = sp.local('harbingerSpotPrice', (spotPrice.value * Constants.PRECISION) // 1_000_000)

    # Check for volatility difference between VWAP and spot
    volatilityDifference = (abs(harbingerVwapPrice - harbingerSpotPrice.value) * 100 // harbingerSpotPrice.value) # because tolerance is a percent
    sp.verify(self.data.volatilityTolerance > volatilityDifference, Errors.VOLATILITY)

    # Upsample
    tokensToTrade = sp.local('tokensToTrade', (self.data.tradeAmount * Constants.PRECISION))

    # Calculate the expected XTZ with no slippage.
    # Expected out with no slippage = (number of tokens to trade // mutez Spot price) / 1e6
    neutralOut = (tokensToTrade.value // spotPrice.value) // 1_000_000

    # Apply spread multiplier
    # Expected out multiplied by spread = (neutral out from above) * (1 + spread amount)
    percent = sp.nat(100) + self.data.spreadAmount
    requiredOut = (neutralOut * percent) // 100 # Note that percent is specified in scale = 100

    # Approve Quipuswap contract to spend on token contract
    approveHandle = sp.contract(
        sp.TPair(sp.TAddress, sp.TNat),
        self.data.tokenAddress,
        "approve"
    ).open_some(message = Errors.APPROVAL)
    approveArg = sp.pair(self.data.quipuswapContractAddress, tokensToTrade.value)
    sp.transfer(approveArg, sp.mutez(0), approveHandle)

    # Invoke a quipuswap trade
    tradeHandle = sp.contract(
      sp.TPair(sp.TPair(sp.TNat, sp.TNat), sp.TAddress),
      self.data.quipuswapContractAddress,
      "tokenToTezPayment"
    ).open_some(message = Errors.DEX_CONTRACT_ERROR)
    tradeArg = sp.pair(sp.pair(tokensToTrade.value, requiredOut), self.data.receiverContractAddress)
    sp.transfer(tradeArg, sp.mutez(0), tradeHandle)

    # Write last trade timestamp to storage
    self.data.lastTradeTime = sp.now


  ################################################################
  #  Balance functions
  ################################################################
  
  # Return FA 1.2 balance to receiverContractAddress
  @sp.entry_point(check_no_incoming_transfer=True)
  def returnBalance(self):

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

    # Update balance
    self.getBalance()

  # Call token contract to update balance.
  def getBalance(self):
    param = (sp.self_address, sp.self_entry_point(entry_point = 'redeemCallback'))
    contractHandle = sp.contract(
      sp.TPair(sp.TAddress, sp.TContract(sp.TNat)),
      self.data.tokenAddress,
      "getBalance",      
    ).open_some()
    sp.transfer(param, sp.mutez(0), contractHandle)

  # Private callback for updating Balance.
  @sp.entry_point(check_no_incoming_transfer=True)
  def redeemCallback(self, updatedBalance):
    sp.set_type(updatedBalance, sp.TNat)

    # Validate sender
    sp.verify(sp.sender == self.data.tokenAddress, Errors.BAD_SENDER)

    self.data.tokenBalance = updatedBalance
    
    # Send balance to Receiver
    sendParam = (
      sp.self_address,
      self.data.receiverContractAddress,
      self.data.tokenBalance
    )

    sendHandle = sp.contract(
      sp.TTuple(sp.TAddress, sp.TAddress, sp.TNat),
      self.data.tokenAddress,
      "transfer"
    ).open_some()
    sp.transfer(sendParam, sp.mutez(0), sendHandle)

  ################################################################
  # Pause Guardian
  ################################################################

  # Pause the system
  @sp.entry_point(check_no_incoming_transfer=True)
  def pause(self):
    sp.verify(sp.sender == self.data.pauseGuardianContractAddress, message = Errors.NOT_PAUSE_GUARDIAN)
    self.data.paused = True

  ################################################################
  # Governance
  ################################################################

  # Update the max data delay (stale data).
  @sp.entry_point(check_no_incoming_transfer=True)
  def setMaxDataDelaySec(self, newMaxDataDelaySec):
    sp.set_type(newMaxDataDelaySec, sp.TNat)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.maxDataDelaySec = newMaxDataDelaySec

  # Update the delay between swaps.
  @sp.entry_point(check_no_incoming_transfer=True)
  def setMinTradeDelaySec(self, newMinTradeDelaySec):
    sp.set_type(newMinTradeDelaySec, sp.TNat)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.minTradeDelaySec = newMinTradeDelaySec

  # Set the trade amount (in normalized tokens).
  @sp.entry_point(check_no_incoming_transfer=True)
  def setTradeAmount(self, newTradeAmount):
    sp.set_type(newTradeAmount, sp.TNat)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.tradeAmount = newTradeAmount

  # Set spread amount (in percent)
  @sp.entry_point(check_no_incoming_transfer=True)
  def setSpreadAmount(self, newSpreadAmount):
    sp.set_type(newSpreadAmount, sp.TNat)
    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.spreadAmount = newSpreadAmount

  # Set volatility tolerance (in percent)
  @sp.entry_point(check_no_incoming_transfer=True)
  def setVolatilityTolerance(self, newVolatilityTolerance):
    sp.set_type(newVolatilityTolerance, sp.TNat)
    
    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.volatilityTolerance = newVolatilityTolerance

  # Unpause the system.
  @sp.entry_point(check_no_incoming_transfer=True)
  def unpause(self):
    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.paused = False

  # Update the Harbinger normalizer contract.
  @sp.entry_point(check_no_incoming_transfer=True)
  def setVwapContract(self, newVwapContractAddress):
    sp.set_type(newVwapContractAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.vwapContractAddress = newVwapContractAddress

  # Update the Harbinger spot contract.
  @sp.entry_point(check_no_incoming_transfer=True)
  def setSpotContract(self, newSpotContractAddress):
    sp.set_type(newSpotContractAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.spotContractAddress = newSpotContractAddress

  # Update the pause guardian contract.
  @sp.entry_point(check_no_incoming_transfer=True)
  def setPauseGuardianContract(self, newPauseGuardianContractAddress):
    sp.set_type(newPauseGuardianContractAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.pauseGuardianContractAddress = newPauseGuardianContractAddress

  # Update the Quipuswap AMM contract.
  @sp.entry_point(check_no_incoming_transfer=True)
  def setQuipuswapContract(self, newQuipuswapContractAddress):
    sp.set_type(newQuipuswapContractAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.quipuswapContractAddress = newQuipuswapContractAddress

  # Update the governor contract.
  @sp.entry_point(check_no_incoming_transfer=True)
  def setGovernorContract(self, newGovernorContractAddress):
    sp.set_type(newGovernorContractAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.governorContractAddress = newGovernorContractAddress
  
  # Update the Receiver contract.                             
  @sp.entry_point(check_no_incoming_transfer=True)
  def setReceiverContract(self, newReceiverContractAddress):
    sp.set_type(newReceiverContractAddress, sp.TAddress)

    sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
    self.data.receiverContractAddress = newReceiverContractAddress


# Only run tests if this file is main.
if __name__ == "__main__":

  ################################################################
  ################################################################
  # Tests
  ################################################################
  ################################################################

  FakeHarbingerVwap = sp.io.import_stored_contract("fake-harbinger-normalizer")
  FakeHarbingerSpot = sp.io.import_stored_contract("fake-harbinger-spot")
  FakeQuipuswap = sp.io.import_stored_contract("fake-quipuswap")


  ################################################################
  # tokenToTezPayment
  ################################################################


  @sp.add_test(name="tokenToTezPayment - correctly calculates amount out with 10 percent spread")
  def test():
    scenario = sp.test_scenario()
    
    # GIVEN a moment in time.
    currentTime = sp.timestamp(1000)
    
    
    # AND fake harbinger normalizer contract
    harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
      harbingerValue = sp.nat(1_000_000), # $1.00
      harbingerUpdateTime = currentTime,
      harbingerAsset = Constants.ASSET_CODE
    )
    scenario += harbingerVwap
    
    # AND fake harbinger spot contract
    harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
      harbingerValue = sp.nat(1_000_000), # $1.00
      harbingerUpdateTime = currentTime,
      harbingerAsset = Constants.ASSET_CODE,
      harbingerVolume = sp.nat(1000)
    )
    scenario += harbingerSpot

    # AND a fake quipuswap contract
    quipuswap = FakeQuipuswap.FakeQuipuswapContract()
    scenario += quipuswap
    
    # AND a Market Making Ceiling contract with 10% spread requirement
    maxDataDelaySec = 60
    minTradeDelaySec = 1
    lastTrade = sp.timestamp(1)
    proxy = MakerContract(
      vwapContractAddress = harbingerVwap.address,
      spotContractAddress = harbingerSpot.address,
      quipuswapContractAddress = quipuswap.address,
      maxDataDelaySec = maxDataDelaySec,
      minTradeDelaySec = minTradeDelaySec,
      lastTradeTime = lastTrade,
      spreadAmount = sp.nat(10),
    )
    scenario += proxy

    # WHEN a trade is initiated
    param = (sp.nat(10), sp.nat(1), Addresses.RECEIVER_ADDRESS)
    amount = sp.nat(10)
    scenario += proxy.tokenToTezPayment().run(
      now = currentTime
    )

    # THEN a trade was attempted requiring a 10% spread between harbinger price and quipuswap price
    # Expected Amount = (tokens sent / harbinger price) * (1 + (spread amount // 100))
    #                 = (10 / $1.00) * (1 + .1)
    #                 = 10 * 1.1
    #                 = 11
    scenario.verify(quipuswap.data.amountOut == 11 * 1_000_000)
    scenario.verify(quipuswap.data.destination == Addresses.RECEIVER_ADDRESS)

  @sp.add_test(name="tokenToTezPayment - correctly calculates amount out with no spread")
  def test():
    scenario = sp.test_scenario()
    
    # GIVEN a moment in time.
    currentTime = sp.timestamp(1000)
    
    # AND fake harbinger normalizer contract
    harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
      harbingerValue = sp.nat(1_000_000), # $1.00
      harbingerUpdateTime = currentTime,
      harbingerAsset = Constants.ASSET_CODE
    )
    scenario += harbingerVwap
    
    # AND fake harbinger spot contract
    harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
      harbingerValue = sp.nat(1_000_000), # $1.00
      harbingerUpdateTime = currentTime,
      harbingerAsset = Constants.ASSET_CODE,
      harbingerVolume = sp.nat(1000)
    )
    scenario += harbingerSpot

    # AND a fake quipuswap contract
    quipuswap = FakeQuipuswap.FakeQuipuswapContract()
    scenario += quipuswap
    
    # AND a Market Making Ceiling contract with 0% spread requirement
    spreadAmount = 0
    maxDataDelaySec = 60
    minTradeDelaySec = 1
    lastTrade = sp.timestamp(1)
    proxy = MakerContract(
      vwapContractAddress = harbingerVwap.address,
      spotContractAddress = harbingerSpot.address,
      quipuswapContractAddress = quipuswap.address,
      maxDataDelaySec = maxDataDelaySec,
      minTradeDelaySec = minTradeDelaySec,
      lastTradeTime = lastTrade,
      spreadAmount = spreadAmount,
    )
    scenario += proxy

    # WHEN a trade is initiated
    scenario += proxy.tokenToTezPayment().run(
      now = currentTime
    )

    # THEN a trade was attempted requiring a 0 spread between harbinger price and quipuswap price
    # Expected Amount = (tokens sent / harbinger price) * (1 + (spread amount / 100))
    #                 = (10 / $1.00) * (1 + 0)
    #                 = 10 * 1
    #                 = 10
    scenario.verify(quipuswap.data.amountOut == 10 * 1_000_000)
    scenario.verify(quipuswap.data.destination == Addresses.RECEIVER_ADDRESS)

  @sp.add_test(name="tokenToTezPayment - fails if oracle is outdated")
  def test():
    scenario = sp.test_scenario()
    
    # GIVEN a moment in time.
    currentTime = sp.timestamp(1000)

    # AND fake harbinger normalizer
    harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
      harbingerValue = sp.nat(3_500_000),
      harbingerAsset = Constants.ASSET_CODE
    )
    scenario += harbingerVwap

    # AND fake harbinger spot contract that is out of date
    lastUpdateTime = sp.timestamp(500)
    harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
      harbingerValue = sp.nat(3_500_000), # $3.50
      harbingerUpdateTime = lastUpdateTime,
      harbingerAsset = Constants.ASSET_CODE
    )
    scenario += harbingerSpot
    
    # AND a Quipuswap Proxy contract with max data delay less than (currentTime - lastUpdateTime)
    maxDataDelaySec = sp.nat(499) # currentTime - lastUpdateTime - 1
    proxy = MakerContract(
      spotContractAddress = harbingerSpot.address,
      vwapContractAddress = harbingerVwap.address,
      maxDataDelaySec = maxDataDelaySec
    )
    scenario += proxy

    # WHEN a trade is initiated
    # THEN the call fails
    scenario += proxy.tokenToTezPayment().run(
      sender = Addresses.NULL_ADDRESS,
      now = currentTime,
      valid = False,
      exception = Errors.STALE_DATA
    )

  @sp.add_test(name="tokenToTezPayment - fails if contract is paused")
  def test():
    # GIVEN a Quipuswap Proxy contract that is paused
    scenario = sp.test_scenario()

    proxy = MakerContract(
      paused = True
    )
    scenario += proxy

    # WHEN a trade is initiated
    # THEN the call fails
    scenario += proxy.tokenToTezPayment().run(
      valid = False,
      exception = Errors.PAUSED
    )

  @sp.add_test(name="tokenToTezPayment - fails if trade is sooner than minimum delay")
  def test():
    # GIVEN a Quipuswap Proxy contract with minimum trade delay of 60 seconds
    scenario = sp.test_scenario()

    delay = 60
    proxy = MakerContract(
      minTradeDelaySec = delay
    )
    scenario += proxy

    # WHEN a trade is initiated at a time sooner than the minimum trade delay
    # THEN the call fails
    stamp = sp.timestamp(delay - 1)

    scenario += proxy.tokenToTezPayment().run(
      now = stamp,
      valid = False,
      exception = Errors.TRADE_TIME
    )

  @sp.add_test(name="tokenToTezPayment - fails if volatility between VWAP and Spot is too great")
  def test():
    scenario = sp.test_scenario()

    # GIVEN a moment in time.
    currentTime = sp.timestamp(1000)
    
    # AND fake harbinger normalizer contract with a price of $1.00
    harbingerVwap = FakeHarbingerVwap.FakeHarbingerContract(
      harbingerValue = sp.nat(1_000_000), # $1.00
      harbingerUpdateTime = currentTime,
      harbingerAsset = Constants.ASSET_CODE
    )
    scenario += harbingerVwap
    
    # AND fake harbinger spot contract with a price of $1.10
    harbingerSpot = FakeHarbingerSpot.FakeHarbingerContract(
      harbingerValue = sp.nat(1_100_000), # $1.10
      harbingerUpdateTime = currentTime,
      harbingerAsset = Constants.ASSET_CODE,
      harbingerVolume = sp.nat(1000)
    )
    scenario += harbingerSpot

    # AND Quipuswap Proxy contract with volatilityTolerance of 5%
    proxy = MakerContract(
      vwapContractAddress = harbingerVwap.address,
      spotContractAddress = harbingerSpot.address,
      volatilityTolerance = 5,
    )
    scenario += proxy

    # WHEN a trade is initiated
    # THEN the call fails
    amount = sp.nat(10)
    scenario += proxy.tokenToTezPayment().run(
      now = currentTime,
      valid = False,
      exception = Errors.VOLATILITY
    )

  ################################################################
  # returnBalance
  ################################################################
  @sp.add_test(name="returnBalance - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    # AND a market making contract
    proxy = MakerContract()
    scenario += proxy

    # WHEN returnBalance is called by the governor THEN the call succeeds
    scenario += proxy.returnBalance().run(
      sender = Addresses.GOVERNOR_ADDRESS,
      valid = True
    )

  @sp.add_test(name="returnBalance - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    # AND a maker contract
    proxy = MakerContract()
    scenario += proxy

    # WHEN returnBalance is called THEN the call fails
    notGovernor = Addresses.NULL_ADDRESS
    scenario += proxy.returnBalance().run(
      sender = notGovernor,
      valid = False
    )

  ################################################################
  # pause
  ################################################################

  @sp.add_test(name="pause - succeeds when called by pause guardian")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      paused = False
    )
    scenario += proxy

    # WHEN pause is called
    scenario += proxy.pause().run(
      sender = Addresses.PAUSE_GUARDIAN_ADDRESS,
    )

    # THEN the contract is paused
    scenario.verify(proxy.data.paused == True)

  @sp.add_test(name="pause - fails when not called by pause guardian")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      paused = False
    )
    scenario += proxy

    # WHEN pause is called is called by someone who isn't the pause guardian THEN the call fails
    scenario += proxy.pause().run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_PAUSE_GUARDIAN
    )

  ################################################################
  # setMaxDataDelaySec
  ################################################################

  @sp.add_test(name="setMaxDataDelaySec - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      maxDataDelaySec = sp.nat(10)
    )
    scenario += proxy

    # WHEN setMaxDataDelaySec is called
    newValue = sp.nat(20)
    scenario += proxy.setMaxDataDelaySec(newValue).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the storage is updated
    scenario.verify(proxy.data.maxDataDelaySec == newValue)

  @sp.add_test(name="setMaxDataDelaySec - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      maxDataDelaySec = sp.nat(10)
    )
    scenario += proxy

    # WHEN setMaxDataDelaySec is called is called by someone who isn't the governor THEN the call fails
    newValue = sp.nat(20)
    scenario += proxy.setMaxDataDelaySec(newValue).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )

  ################################################################
  # setMinTradeDelaySec
  ################################################################

  @sp.add_test(name="setMinTradeDelaySec - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      minTradeDelaySec = sp.nat(10)
    )
    scenario += proxy

    # WHEN setMinTradeDelaySec is called
    newValue = sp.nat(20)
    scenario += proxy.setMinTradeDelaySec(newValue).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the storage is updated
    scenario.verify(proxy.data.minTradeDelaySec == newValue)

  @sp.add_test(name="setMinTradeDelaySec - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      maxDataDelaySec = sp.nat(10)
    )
    scenario += proxy

    # WHEN setMinTradeDelaySec is called is called by someone who isn't the governor THEN the call fails
    newValue = sp.nat(20)
    scenario += proxy.setMinTradeDelaySec(newValue).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )
    
  ################################################################
  # setSpreadAmount
  ################################################################

  @sp.add_test(name="setSpreadAmount - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      spreadAmount = sp.nat(10)
    )
    scenario += proxy

    # WHEN setSpreadAmount is called
    newValue = sp.nat(20)
    scenario += proxy.setSpreadAmount(newValue).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the storage is updated
    scenario.verify(proxy.data.spreadAmount == newValue)

  @sp.add_test(name="setSpreadAmount - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      spreadAmount = sp.nat(10)
    )
    scenario += proxy

    # WHEN setSpreadAmount is called is called by someone who isn't the governor THEN the call fails
    newValue = sp.nat(20)
    scenario += proxy.setSpreadAmount(newValue).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )

  ################################################################
  # setVolatilityTolerance
  ################################################################

  @sp.add_test(name="setVolatilityTolerance - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      volatilityTolerance = sp.nat(10)
    )
    scenario += proxy

    # WHEN setVolatilityTolerance is called
    newValue = sp.nat(20)
    scenario += proxy.setVolatilityTolerance(newValue).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the storage is updated
    scenario.verify(proxy.data.volatilityTolerance == newValue)

  @sp.add_test(name="setVolatilityTolerance - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      volatilityTolerance = sp.nat(10)
    )
    scenario += proxy

    # WHEN setVolatilityTolerance is called is called by someone who isn't the governor THEN the call fails
    newValue = sp.nat(20)
    scenario += proxy.setVolatilityTolerance(newValue).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )

  ################################################################
  # setTradeAmount
  ################################################################

  @sp.add_test(name="setTradeAmount - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      tradeAmount = sp.nat(10)
    )
    scenario += proxy

    # WHEN setTradeAmount is called
    newValue = sp.nat(20)
    scenario += proxy.setTradeAmount(newValue).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the storage is updated
    scenario.verify(proxy.data.tradeAmount == newValue)

  @sp.add_test(name="setTradeAmount - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      tradeAmount = sp.nat(10)
    )
    scenario += proxy

    # WHEN setTradeAmount is called is called by someone who isn't the governor THEN the call fails
    newValue = sp.nat(20)
    scenario += proxy.setTradeAmount(newValue).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )

  ################################################################
  # unpause
  ################################################################

  @sp.add_test(name="unpause - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      paused = True
    )
    scenario += proxy

    # WHEN unpause is called
    scenario += proxy.unpause().run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the contract is unpaused
    scenario.verify(proxy.data.paused == False)

  @sp.add_test(name="unpause - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    proxy = MakerContract(
      paused = True
    )
    scenario += proxy

    # WHEN unpause is called is called by someone who isn't the governor THEN the call fails
    scenario += proxy.unpause().run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )

  ################################################################
  # setSpotContract
  ################################################################

  @sp.add_test(name="setSpotContract - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    spotContractAddress = Addresses.HARBINGER_SPOT_ADDRESS
    proxy = MakerContract(
      spotContractAddress = spotContractAddress
    )
    scenario += proxy

    # WHEN setSpotContract is called with a new contract
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setSpotContract(rotatedAddress).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the contract is updated.
    scenario.verify(proxy.data.spotContractAddress == rotatedAddress)

  @sp.add_test(name="setSpotContract - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    spotContractAddress = Addresses.HARBINGER_SPOT_ADDRESS
    proxy = MakerContract(
      spotContractAddress = spotContractAddress
    )
    scenario += proxy

    # WHEN setSpotContract is called by someone who isn't the governor THEN the call fails
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setSpotContract(rotatedAddress).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )

  ################################################################
  # setVwapContract
  ################################################################

  @sp.add_test(name="setVwapContract - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    vwapContractAddress = Addresses.HARBINGER_VWAP_ADDRESS
    proxy = MakerContract(
      vwapContractAddress = vwapContractAddress
    )
    scenario += proxy

    # WHEN setVwapContract is called with a new contract
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setVwapContract(rotatedAddress).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the contract is updated.
    scenario.verify(proxy.data.vwapContractAddress == rotatedAddress)

  @sp.add_test(name="setVwapContract - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    vwapContractAddress = Addresses.HARBINGER_VWAP_ADDRESS
    proxy = MakerContract(
      vwapContractAddress = vwapContractAddress
    )
    scenario += proxy

    # WHEN setVwapContract is called by someone who isn't the governor THEN the call fails
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setVwapContract(rotatedAddress).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )

  ################################################################
  # setPauseGuardianContract
  ################################################################

  @sp.add_test(name="setPauseGuardianContract - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    pauseGuardianContractAddress = Addresses.PAUSE_GUARDIAN_ADDRESS
    proxy = MakerContract(
      pauseGuardianContractAddress = pauseGuardianContractAddress
    )
    scenario += proxy

    # WHEN setPauseGuardianContract is called with a new contract
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setPauseGuardianContract(rotatedAddress).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the contract is updated.
    scenario.verify(proxy.data.pauseGuardianContractAddress == rotatedAddress)

  @sp.add_test(name="setPauseGuardianContract - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    pauseGuardianContractAddress = Addresses.PAUSE_GUARDIAN_ADDRESS
    proxy = MakerContract(
      pauseGuardianContractAddress = pauseGuardianContractAddress
    )
    scenario += proxy

    # WHEN setPauseGuardianContract is called by someone who isn't the governor THEN the call fails
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setPauseGuardianContract(rotatedAddress).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    ) 

  ################################################################
  # setQuipuswapContract
  ################################################################

  @sp.add_test(name="setQuipuswapContract - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    quipuswapContractAddress = Addresses.QUIPUSWAP_ADDRESS
    proxy = MakerContract(
      quipuswapContractAddress = quipuswapContractAddress
    )
    scenario += proxy

    # WHEN setQuipuswapContract is called with a new contract
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setQuipuswapContract(rotatedAddress).run(
      sender = Addresses.GOVERNOR_ADDRESS,
    )

    # THEN the contract is updated.
    scenario.verify(proxy.data.quipuswapContractAddress == rotatedAddress)

  @sp.add_test(name="setQuipuswapContract - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    governorContractAddress = Addresses.GOVERNOR_ADDRESS
    quipuswapContractAddress = Addresses.QUIPUSWAP_ADDRESS
    proxy = MakerContract(
      quipuswapContractAddress = quipuswapContractAddress
    )
    scenario += proxy

    # WHEN setQuipuswapContract is called by someone who isn't the governor THEN the call fails
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setQuipuswapContract(rotatedAddress).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    ) 

  ################################################################
  # setGovernorContract
  ################################################################

  @sp.add_test(name="setGovernorContract - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    governorContractAddress = Addresses.GOVERNOR_ADDRESS
    proxy = MakerContract(
      governorContractAddress = governorContractAddress
    )
    scenario += proxy

    # WHEN setGovernorContract is called with a new contract
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setGovernorContract(rotatedAddress).run(
      sender = governorContractAddress,
    )

    # THEN the contract is updated.
    scenario.verify(proxy.data.governorContractAddress == rotatedAddress)

  @sp.add_test(name="setGovernorContract - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    governorContractAddress = Addresses.GOVERNOR_ADDRESS
    proxy = MakerContract(
      governorContractAddress = governorContractAddress
    )
    scenario += proxy

    # WHEN setGovernorContract is called by someone who isn't the governor THEN the call fails
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setGovernorContract(rotatedAddress).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )    

  ################################################################
  # setReceiverContract
  ################################################################

  @sp.add_test(name="setReceiverContract - succeeds when called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    governorContractAddress = Addresses.GOVERNOR_ADDRESS
    proxy = MakerContract(
      governorContractAddress = governorContractAddress
    )
    scenario += proxy

    # WHEN setReceiverContract is called with a new contract
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setReceiverContract(rotatedAddress).run(
      sender = governorContractAddress,
    )

    # THEN the contract is updated.
    scenario.verify(proxy.data.receiverContractAddress == rotatedAddress)

  @sp.add_test(name="setReceiverContract - fails when not called by governor")
  def test():
    # GIVEN a Quipuswap Proxy contract
    scenario = sp.test_scenario()

    governorContractAddress = Addresses.GOVERNOR_ADDRESS
    proxy = MakerContract(
      governorContractAddress = governorContractAddress
    )
    scenario += proxy

    # WHEN setReceiverContract is called by someone who isn't the governor THEN the call fails
    rotatedAddress = Addresses.ROTATED_ADDRESS
    scenario += proxy.setReceiverContract(rotatedAddress).run(
      sender = Addresses.NULL_ADDRESS,
      valid = False,
      exception = Errors.NOT_GOVERNOR
    )    

  sp.add_compilation_target("quipu_swapper", MakerContract())
