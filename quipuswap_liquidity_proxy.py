import smartpy as sp

Addresses = sp.io.import_script_from_url("file:common/addresses.py")
Constants = sp.io.import_script_from_url("file:common/constants.py")
Errors = sp.io.import_script_from_url("file:common/errors.py")

################################################################
# State Machine
################################################################

IDLE = 0
WAITING_FOR_TOKEN_BALANCE = 1

################################################################
# Contract
################################################################

# Creates a liquidity fund contract for managing liquidity on a Quipuswap pair.
# Allows the "Executor" address to add liquidity to Quipuswap and veto.
# Allows the "Governor" address to remove liquidity, claim rewards, vote, 
#   transfer tokens or XTZ, and change addresses.

class LiquidityFundContract(sp.Contract):
    def __init__(
        self,
        governorContractAddress = Addresses.GOVERNOR_ADDRESS,
        executorContractAddress = Addresses.EXECUTOR_ADDRESS,
        tokenContractAddress = Addresses.TOKEN_ADDRESS,
        quipuswapContractAddress = Addresses.QUIPUSWAP_ADDRESS,
        harbingerContractAddress = Addresses.HARBINGER_VWAP_ADDRESS,

        slippageTolerance = sp.nat(5), # 5%
        maxDataDelaySec = sp.nat(60 * 5), # 5 minutes
        
        state = IDLE,
        sendAllTokens_destination = sp.none,
        **extra_storage
    ):
        self.exception_optimization_level = "DefaultUnit"

        self.init(
            governorContractAddress = governorContractAddress,
            executorContractAddress = executorContractAddress,
            tokenContractAddress = tokenContractAddress,
            quipuswapContractAddress = quipuswapContractAddress,
            harbingerContractAddress = harbingerContractAddress,

            slippageTolerance = slippageTolerance,
            maxDataDelaySec = maxDataDelaySec,

            # State machine
            state = state,
            sendAllTokens_destination = sendAllTokens_destination,

            **extra_storage
        )

    ################################################################
    # Public API
    ################################################################

    # Allow XTZ transfers into the fund.
    @sp.entry_point
    def default(self):
        pass

    ################################################################
    # Quipuswap API
    ################################################################

    @sp.entry_point
    def addLiquidity(self, param):
        sp.set_type(param, sp.TRecord(tokens = sp.TNat, mutez = sp.TNat).layout(("tokens", "mutez")))

        # Verify the caller is the permissioned executor account.
        sp.verify(sp.sender == self.data.executorContractAddress, message = Errors.NOT_EXECUTOR)

        # Destructure parameters.
        tokensToAdd = param.tokens
        mutezToAdd = param.mutez

        # Read vwap from Harbinger Normalizer views
        harbingerVwap = sp.view(
            "getPrice",
            self.data.harbingerContractAddress,
            Constants.ASSET_CODE,
            sp.TPair(sp.TTimestamp, sp.TNat)
        ).open_some(message = Errors.VWAP_VIEW_ERROR)

        harbingerPrice = sp.snd(harbingerVwap)

        # Calculate input price to compare to Harbinger
        inputPrice = tokensToAdd // mutezToAdd // 1000000

        # Calculate percentage difference between Harbinger and function input
        percentageDifference = abs(harbingerPrice - inputPrice) * 100 // harbingerPrice
        # Assert that difference is within range of slippageTolerance
        sp.verify(self.data.slippageTolerance > percentageDifference, Errors.SLIPPAGE)

        # Assert that the Harbinger data is newer than max data delay
        dataAge = sp.as_nat(sp.now - sp.fst(harbingerVwap))
        sp.verify(dataAge <= self.data.maxDataDelaySec, Errors.STALE_DATA)
        
        # Approve Quipuswap contract to spend on token contract
        approveHandle = sp.contract(
            sp.TPair(sp.TAddress, sp.TNat),
            self.data.tokenContractAddress,
            "approve"
        ).open_some(message = Errors.APPROVAL)
        approveArg = sp.pair(self.data.quipuswapContractAddress, tokensToAdd)
        sp.transfer(approveArg, sp.mutez(0), approveHandle)

        # Add the liquidity to the Quipuswap contract.
        addHandle = sp.contract(
            sp.TNat,
            self.data.quipuswapContractAddress,
            "investLiquidity"
        ).open_some(message = Errors.DEX_CONTRACT_ERROR)
        sp.transfer(tokensToAdd, sp.utils.nat_to_mutez(mutezToAdd), addHandle)
    
    @sp.entry_point
    def removeLiquidity(self, param):
        sp.set_type(param, sp.TRecord(
            min_mutez_out = sp.TNat, 
            min_tokens_out = sp.TNat, 
            lp_to_remove = sp.TNat
            ).layout((("min_mutez_out", "min_tokens_out"), ("lp_to_remove"))))

        # Verify the caller is the governor address
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

        # Destructure parameters
        minMutez = param.min_mutez_out
        minTokens = param.min_tokens_out
        amountToRemove = param.lp_to_remove

        # Remove liquidity from the Quipuswap contract
        divestHandle = sp.contract(
            sp.TPair(sp.TPair(sp.TNat, sp.TNat), sp.TNat),
            self.data.quipuswapContractAddress,
            "divestLiquidity"
        ).open_some(message = Errors.DEX_CONTRACT_ERROR)
        arg = sp.pair(sp.pair(minMutez, minTokens), amountToRemove)
        sp.transfer(arg, sp.mutez(0), divestHandle)

    @sp.entry_point
    def claimRewards(self):

        # Verify the caller is the governor address
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

        address = sp.self_address

        # Claim rewards from the Quipuswap contract
        claimHandle = sp.contract(
            sp.TAddress,
            self.data.quipuswapContractAddress,
            "withdrawProfit"
        ).open_some(message = Errors.DEX_CONTRACT_ERROR)
        sp.transfer(address, sp.mutez(0), claimHandle) 

    @sp.entry_point
    def vote(self, param):
        sp.set_type(param, sp.TRecord(
            candidate = sp.TKeyHash,
            value = sp.TNat,
            voter = sp.TAddress
        ).layout((("candidate", "value"), ("voter"))))
        
        # Verify the caller is the governor address
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)


        # Call vote() on Quipuswap AMM
        voteHandle = sp.contract(
            sp.TPair(sp.TPair(sp.TKeyHash, sp.TNat), sp.TAddress),
            self.data.quipuswapContractAddress,
            "vote"
        ).open_some(message = Errors.DEX_CONTRACT_ERROR)
        arg = sp.pair(sp.pair(param.candidate, param.value), param.voter)
        sp.transfer(arg, sp.mutez(0), voteHandle)
    
    @sp.entry_point
    def veto(self, param):
        sp.set_type(param, sp.TRecord(
            value = sp.TNat,
            voter = sp.TAddress
        ).layout((("value", "voter"))))

        # Verify the caller is the executor address
        sp.verify(sp.sender == self.data.executorContractAddress, message = Errors.NOT_EXECUTOR)

        # Call veto() on Quipuswap AMM
        vetoHandle = sp.contract(
            sp.TPair(sp.TNat,sp.TAddress),
            self.data.quipuswapContractAddress,
            "veto"
        ).open_some(message = Errors.DEX_CONTRACT_ERROR)
        arg = sp.pair(param.value,param.voter)
        sp.transfer(arg, sp.mutez(0), vetoHandle) 


    ################################################################
    # Governance
    ################################################################

    @sp.entry_point
    def setDelegate(self, newDelegate):
        sp.set_type(newDelegate, sp.TOption(sp.TKeyHash))

        # Verify the caller is the governor.
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

        sp.set_delegate(newDelegate)

    # Governance is timelocked and can always transfer funds.
    @sp.entry_point
    def send(self, param):
        sp.set_type(param, sp.TPair(sp.TMutez, sp.TAddress))

        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
        sp.send(sp.snd(param), sp.fst(param))

    # Governance is timelocked and can always transfer funds.
    @sp.entry_point
    def sendAll(self, destination):
        sp.set_type(destination, sp.TAddress)

        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
        sp.send(destination, sp.balance)        

    # Governance is timelocked and can always transfer funds.
    @sp.entry_point
    def sendTokens(self, param):
        sp.set_type(param, sp.TPair(sp.TNat, sp.TAddress))

        # Verify sender is governor.
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

        # Destructure parameters.
        amount = sp.fst(param)
        destination = sp.snd(param)

        # Invoke token contract
        tokenContractParam = sp.record(
            to_ = destination,
            from_ = sp.self_address,
            value = amount
        )
        contractHandle = sp.contract(
            sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
            self.data.tokenContractAddress,
            "transfer"
        ).open_some()
        sp.transfer(tokenContractParam, sp.mutez(0), contractHandle)

    # Transfer the entire balance of kUSD
    @sp.entry_point
    def sendAllTokens(self, destination):
        sp.set_type(destination, sp.TAddress)

        # Verify sender is governor.
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

        # Verify state is correct.
        sp.verify(self.data.state == IDLE, message = Errors.BAD_STATE)

        # Call token contract to get the balance
        tokenContractHandle = sp.contract(
            sp.TPair(
                sp.TAddress,
                sp.TContract(sp.TNat),
            ),
            self.data.tokenContractAddress,
            "getBalance"
        ).open_some()
        tokenContractArg = (
            sp.self_address,
            sp.self_entry_point(entry_point = "sendAllTokens_callback")
        )
        sp.transfer(tokenContractArg, sp.mutez(0), tokenContractHandle)

        # Save state to state machine
        self.data.state = WAITING_FOR_TOKEN_BALANCE
        self.data.sendAllTokens_destination = sp.some(destination)      

    # Private callback for `sendAllTokens`
    @sp.entry_point
    def sendAllTokens_callback(self, tokenBalance):
        sp.set_type(tokenBalance, sp.TNat)

        # Verify sender is the token contract
        sp.verify(sp.sender == self.data.tokenContractAddress, message = Errors.BAD_SENDER)

        # Verify state is correct.
        sp.verify(self.data.state == WAITING_FOR_TOKEN_BALANCE, message = Errors.BAD_STATE)

        # Unwrap saved parameters.
        destination = self.data.sendAllTokens_destination.open_some()

        # Invoke token contract
        tokenContractParam = sp.record(
            to_ = destination,
            from_ = sp.self_address,
            value = tokenBalance
        )
        contractHandle = sp.contract(
            sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
            self.data.tokenContractAddress,
            "transfer"
        ).open_some()
        sp.transfer(tokenContractParam, sp.mutez(0), contractHandle)

        # Reset state
        self.data.state = IDLE
        self.data.sendAllTokens_destination = sp.none      

    # Rescue FA1.2 Tokens
    @sp.entry_point
    def rescueFA12(self, params):
        sp.set_type(params, sp.TRecord(
            tokenContractAddress = sp.TAddress,
            amount = sp.TNat,
            destination = sp.TAddress,
        ).layout(("tokenContractAddress", ("amount", "destination"))))

        # Verify sender is governor.
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

        # Transfer the tokens
        handle = sp.contract(
            sp.TRecord(
                from_ = sp.TAddress,
                to_ = sp.TAddress, 
                value = sp.TNat
            ).layout(("from_ as from", ("to_ as to", "value"))),
            params.tokenContractAddress,
            "transfer"
        ).open_some()
        arg = sp.record(from_ = sp.self_address, to_ = params.destination, value = params.amount)
        sp.transfer(arg, sp.mutez(0), handle)

    # Rescue FA2 tokens
    @sp.entry_point
    def rescueFA2(self, params):
        sp.set_type(params, sp.TRecord(
            tokenContractAddress = sp.TAddress,
            tokenId = sp.TNat,
            amount = sp.TNat,
            destination = sp.TAddress,
        ).layout(("tokenContractAddress", ("tokenId", ("amount", "destination")))))

        # Verify sender is governor.
        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)

        # Transfer the tokens
        handle = sp.contract(
            sp.TList(
                sp.TRecord(
                    from_ = sp.TAddress,
                    txs = sp.TList(
                        sp.TRecord(
                            amount = sp.TNat,
                            to_ = sp.TAddress, 
                            token_id = sp.TNat,
                        ).layout(("to_", ("token_id", "amount")))
                    )
                ).layout(("from_", "txs"))
            ),
            params.tokenContractAddress,
            "transfer"
        ).open_some()

        arg = [
            sp.record(
            from_ = sp.self_address,
            txs = [
                sp.record(
                    amount = params.amount,
                    to_ = params.destination,
                    token_id = params.tokenId
                )
            ]
            )
        ]
        sp.transfer(arg, sp.mutez(0), handle)                

    # Update the governor contract.
    @sp.entry_point
    def setGovernorContract(self, newGovernorContractAddress):
        sp.set_type(newGovernorContractAddress, sp.TAddress)

        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
        self.data.governorContractAddress = newGovernorContractAddress

    # Update the executor contract.
    @sp.entry_point
    def setExecutorContract(self, newExecutorContractAddress):
        sp.set_type(newExecutorContractAddress, sp.TAddress)

        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
        self.data.executorContractAddress = newExecutorContractAddress
    
    # Set slippage tolerance (in percent)
    @sp.entry_point
    def setSlippageTolerance(self, newSlippageTolerance):
        sp.set_type(newSlippageTolerance, sp.TNat)

        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
        self.data.slippageTolerance = newSlippageTolerance

    # Set maximum oracle data delay in seconds
    @sp.entry_point
    def setMaxDataDelaySec(self, newMaxDataDelaySec):
        sp.set_type(newMaxDataDelaySec, sp.TNat)

        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
        self.data.maxDataDelaySec = newMaxDataDelaySec

    # Update the harbinger normalizer contract.
    @sp.entry_point
    def setHarbingerContract(self, newHarbingerContractAddress):
        sp.set_type(newHarbingerContractAddress, sp.TAddress)

        sp.verify(sp.sender == self.data.governorContractAddress, message = Errors.NOT_GOVERNOR)
        self.data.harbingerContractAddress = newHarbingerContractAddress

# Only run tests if this file is main.
if __name__ == "__main__":

    # ################################################################
    # ################################################################
    # # Tests
    # ################################################################
    # ################################################################

    DummyContract = sp.io.import_script_from_url("file:test-helpers/dummy-contract.py")
    FA12 = sp.io.import_script_from_url("file:test-helpers/fa12.py")
    FA2 = sp.io.import_script_from_url("file:test-helpers/fa2.py")
    Token = sp.io.import_script_from_url("file:test-helpers/token.py")
    FakeQuipuswap = sp.io.import_script_from_url("file:test-helpers/fake-quipuswap.py")
    FakeHarbinger = sp.io.import_script_from_url("file:test-helpers/fake-harbinger-normalizer.py")

    ################################################################
    # default
    ################################################################

    @sp.add_test(name="default - can receive funds")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	fund = LiquidityFundContract()
    	scenario += fund

    	# WHEN the default entry point is called
    	amount = sp.mutez(1)
    	scenario += fund.default(sp.unit).run(
    		amount = amount,
    	)

    	# THEN the funds are accepted.
    	scenario.verify(fund.balance == amount)

    ################################################################
    #addLiquidity
    ################################################################
    @sp.add_test(name="addLiquidity - fails when not called by executor")
    def test():
        # GIVEN a LiquidityFund with an executor
        scenario = sp.test_scenario()
        executor = Addresses.EXECUTOR_ADDRESS

        fund = LiquidityFundContract(
            executorContractAddress = executor
        )
        scenario += fund

        # WHEN addLiquidity is called by someone other than the executor THEN the invocation fails.
        tokens = 2 * Constants.PRECISION
        mutez = 1000000
        notExecutor = Addresses.NULL_ADDRESS
        scenario += fund.addLiquidity(mutez=mutez,tokens=tokens).run(
            sender = notExecutor,
            valid = False
        )

    @sp.add_test(name="addLiquidity - fails when oracle data is stale")
    def test():
        
        # GIVEN a moment in time
        scenario = sp.test_scenario()
        currentTime = sp.timestamp(1000)
        delay = sp.nat(60)
        
        # AND a Harbinger Normalizer contract with timestamp older than (current time - max delay - 1)
        normalizer = FakeHarbinger.FakeHarbingerContract(
            harbingerUpdateTime = sp.timestamp(939), # currentTime - delay - 1
            harbingerValue = sp.nat(2000000))
        scenario += normalizer

        # AND a LiquidityFund with an executor and max data delay of 60 seconds
        
        executor = Addresses.EXECUTOR_ADDRESS


        fund = LiquidityFundContract(
            executorContractAddress = executor,
            harbingerContractAddress = normalizer.address,
            slippageTolerance = 5,
            maxDataDelaySec = delay
        )
        scenario += fund

        # WHEN addLiquidity is called by the executor THEN the invocation fails.
        tokens = 2 * Constants.PRECISION
        mutez = 1000000
        scenario += fund.addLiquidity(mutez=mutez,tokens=tokens).run(
            sender = executor,
            now = currentTime,
            valid = False,
            exception = Errors.STALE_DATA
        )    


    @sp.add_test(name="addLiquidity - fails when input ratio is outside of bounds")
    def test():
        
        # GIVEN a moment in time
        scenario = sp.test_scenario()
        currentTime = sp.timestamp(1000)
        delay = sp.nat(60)
        
        # AND a Harbinger Normalizer contract with current timestamp and price of $5.00
        normalizer = FakeHarbinger.FakeHarbingerContract(
            harbingerUpdateTime = currentTime,
            harbingerValue = sp.nat(5000000))
        scenario += normalizer

        # AND a LiquidityFund with a slippageTolerance of 5%
        executor = Addresses.EXECUTOR_ADDRESS
        fund = LiquidityFundContract(
            harbingerContractAddress = normalizer.address,
            slippageTolerance = 5
        )

        scenario += fund

        # WHEN addLiquidity is called by the executor with a price of $2.00 THEN the invocation fails.       
        tokens = 2 * Constants.PRECISION
        mutez = 1000000
        scenario += fund.addLiquidity(mutez=mutez,tokens=tokens).run(
            sender = executor,
            now = currentTime,
            valid = False,
            exception = Errors.SLIPPAGE
        )

    @sp.add_test(name="addLiquidity - calls the Quipuswap AMM when input ratio is within bounds")
    def test():
        
        # GIVEN a moment in time
        scenario = sp.test_scenario()
        currentTime = sp.timestamp(1000)
        delay = sp.nat(60)
        
        # AND a Harbinger Normalizer contract with current timestamp and price of $2.00
        normalizer = FakeHarbinger.FakeHarbingerContract(
            harbingerUpdateTime = currentTime,
            harbingerValue = sp.nat(2000000))
        scenario += normalizer
   
    	# AND a Token contract.
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

        # AND a Quipuswap AMM contract
        quipuswap = FakeQuipuswap.FakeQuipuswapContract()
        scenario += quipuswap

        # AND a LiquidityFund with a slippageTolerance of 5%,a balance of 1000000 mutez, and an executor.
        balance = sp.mutez(1000000)
        executor = Addresses.EXECUTOR_ADDRESS
        fund = LiquidityFundContract(
            harbingerContractAddress = normalizer.address,
            quipuswapContractAddress = quipuswap.address,
            executorContractAddress = executor,
            slippageTolerance = 5
        )
        fund.set_initial_balance(balance)
        scenario += fund

    	# AND the fund has $2 of tokens.
    	fundTokens = 2 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

        # WHEN addLiquidity is called by the executor with a price of $2.00 THEN the invocation succeeds.
        
        tokens = 2 * Constants.PRECISION
        mutez = 1000000

        scenario += fund.addLiquidity(mutez=mutez,tokens=tokens).run(
            sender = executor,
            now = currentTime,
            valid = True
        )
        # Verify parameters were sent
        scenario.verify(quipuswap.balance == sp.mutez(mutez))
        scenario.verify(quipuswap.data.amountInvested == tokens)

    ################################################################
    # removeLiquidity
    ################################################################
    @sp.add_test(name="removeLiquidity - fails when not called by governor")

    def test():
        # GIVEN a LiquidityFund with a governor
        scenario = sp.test_scenario()
        governor = Addresses.GOVERNOR_ADDRESS

        fund = LiquidityFundContract(
            governorContractAddress = governor
        )
        scenario += fund

        # WHEN removeLiquidity is called by someone other than the governor THEN the invocation fails.
        tokens = 2 * Constants.PRECISION
        mutez = 1000000
        lp = 100000000
        notGovernor = Addresses.NULL_ADDRESS
        scenario += fund.removeLiquidity(lp_to_remove=lp,min_mutez_out=mutez,min_tokens_out=tokens).run(
            sender = notGovernor,
            valid = False
        )

    @sp.add_test(name="removeLiquidity - succeeds when called by governor")
    def test():
        # GIVEN a LiquidityFund with a governor
        scenario = sp.test_scenario()
        governor = Addresses.GOVERNOR_ADDRESS

        fund = LiquidityFundContract(
            governorContractAddress = governor
        )
        scenario += fund

        # WHEN removeLiquidity is called by the governor THEN the invocation succeeds.
        tokens = 2000000000000000000
        mutez = 1000000
        lp = 100000000
        scenario += fund.removeLiquidity(lp_to_remove=lp,min_mutez_out=mutez,min_tokens_out=tokens).run(
            sender = governor,
            valid = True
        )

    ################################################################
    # claimRewards
    ################################################################

    @sp.add_test(name="claimRewards - fails when not called by governor")
    def test():
        # GIVEN a LiquidityFund with a governor
        scenario = sp.test_scenario()
        governor = Addresses.GOVERNOR_ADDRESS

        fund = LiquidityFundContract(
            governorContractAddress = governor
        )
        scenario += fund

        # WHEN claimRewards is called by someone other than the governor THEN the invocation fails.
        notGovernor = Addresses.NULL_ADDRESS
        scenario += fund.claimRewards().run(
            sender = notGovernor,
            valid = False
        )

    @sp.add_test(name="claimRewards - succeeds when called by governor")
    def test():
        # GIVEN a LiquidityFund with a governor
        scenario = sp.test_scenario()
        governor = Addresses.GOVERNOR_ADDRESS

        fund = LiquidityFundContract(
            governorContractAddress = governor
        )
        scenario += fund

        # WHEN claimRewards is called by  the governor THEN the invocation succeeds.
        scenario += fund.claimRewards().run(
            sender = governor,
            valid = True
        )

    ################################################################
    # vote
    ################################################################
    @sp.add_test(name="vote - fails when not called by governor")
    def test():
        # GIVEN a LiquidityFund with a governor
        scenario = sp.test_scenario()
        governor = Addresses.GOVERNOR_ADDRESS

        fund = LiquidityFundContract(
            governorContractAddress = governor
        )
        scenario += fund

        # WHEN vote is called by someone other than the governor THEN the invocation fails.
        notGovernor = Addresses.NULL_ADDRESS
        some_key_hash = Addresses.BAKER_KEY_HASH
        some_value = sp.nat(1000000)
        self_addr = governor
        param = sp.record(
            candidate = some_key_hash, 
            value = some_value,
            voter = self_addr
            )
        scenario += fund.vote(param).run(
            sender = notGovernor,
            valid = False
        )

    @sp.add_test(name="vote - succeeds when called by governor")
    def test():
        # GIVEN a LiquidityFund with a governor
        scenario = sp.test_scenario()
        governor = Addresses.GOVERNOR_ADDRESS

        fund = LiquidityFundContract(
            governorContractAddress = governor
        )
        scenario += fund

        # WHEN vote is called by the governor THEN the invocation succeeds.
        
        some_key_hash = Addresses.BAKER_KEY_HASH
        some_value = sp.nat(1000000)
        self_addr = governor
        param = sp.record(
            candidate = some_key_hash, 
            value = some_value,
            voter = self_addr
            )
        scenario += fund.vote(param).run(
            sender = governor,
            valid = True
        )

    @sp.add_test(name="vote - passes correct parameters")
    def test():
        scenario = sp.test_scenario()

        # GIVEN a Quipuswap AMM contract
        quipuswap = FakeQuipuswap.FakeQuipuswapContract()
        scenario += quipuswap

        # AND a LiquidityFund with a governor
        governor = Addresses.GOVERNOR_ADDRESS
        fund = LiquidityFundContract(
            governorContractAddress = governor,
            quipuswapContractAddress = quipuswap.address
        )
        scenario += fund

        # WHEN vote is called by the governor THEN the invocation passes parameters to the Quipuswap AMM.
        someValue = sp.nat(1000000)
        selfAddr = governor
        bakerHash = Addresses.BAKER_KEY_HASH
        param = sp.record( 
            candidate = bakerHash,
            value = someValue,
            voter = selfAddr
            )         
        scenario += fund.vote(param).run(
            sender = governor,
        )
        scenario.verify(quipuswap.data.voteAmount == someValue)
        scenario.verify(quipuswap.data.voteCandidate == bakerHash)
        scenario.verify(quipuswap.data.voteAddress == selfAddr)
        
    ################################################################
    # veto
    ################################################################
    @sp.add_test(name="veto - fails when not called by executor")
    def test():
        # GIVEN a LiquidityFund with an executor
        scenario = sp.test_scenario()
        executor = Addresses.EXECUTOR_ADDRESS

        fund = LiquidityFundContract(
            executorContractAddress = executor
        )
        scenario += fund

        # WHEN veto is called by someone other than the executor THEN the invocation fails.
        notExecutor = Addresses.NULL_ADDRESS
        some_value = sp.nat(1000000)
        self_addr = executor
        param = sp.record( 
            value = some_value,
            voter = self_addr
            )                
        scenario += fund.veto(param).run(
            sender = notExecutor,
            valid = False
        )

    @sp.add_test(name="veto - succeeds when called by executor")
    def test():
        # GIVEN a LiquidityFund with a executor
        scenario = sp.test_scenario()
        executor = Addresses.EXECUTOR_ADDRESS

        fund = LiquidityFundContract(
            executorContractAddress = executor
        )
        scenario += fund

        # WHEN veto is called by  the executor THEN the invocation succeeds.
        some_value = sp.nat(1000000)
        self_addr = executor
        param = sp.record( 
            value = some_value,
            voter = self_addr
            )         
        scenario += fund.veto(param).run(
            sender = executor,
            valid = True
        )
        
    @sp.add_test(name="veto - passes correct parameters")
    def test():
        scenario = sp.test_scenario()

        # GIVEN a Quipuswap AMM contract
        quipuswap = FakeQuipuswap.FakeQuipuswapContract()
        scenario += quipuswap

        # AND a LiquidityFund with a executor
        executor = Addresses.EXECUTOR_ADDRESS
        fund = LiquidityFundContract(
            executorContractAddress = executor,
            quipuswapContractAddress = quipuswap.address
        )
        scenario += fund

        # WHEN veto is called by  the executor THEN the invocation passes parameters to the Quipuswap AMM.
        someValue = sp.nat(1000000)
        selfAddr = executor
        param = sp.record( 
            value = someValue,
            voter = selfAddr
            )         
        scenario += fund.veto(param).run(
            sender = executor,
        )
        scenario.verify(quipuswap.data.vetoAmount == someValue)
        scenario.verify(quipuswap.data.vetoAddress == selfAddr)
        
    ################################################################
    # setDelegate
    ################################################################

    @sp.add_test(name="setDelegate - fails when not called by governor")
    def test():
    	# GIVEN a LiquidityFund without a delegate and a governor.
    	scenario = sp.test_scenario()
    	governor = Addresses.GOVERNOR_ADDRESS

    	fund = LiquidityFundContract(
    		governorContractAddress = governor
    	)
    	scenario += fund

    	# WHEN setDelegate is called by someone other than the governor THEN the invocation fails.
    	notGovernor = Addresses.NULL_ADDRESS
    	delegate = sp.some(Addresses.BAKER_KEY_HASH)
    	scenario += fund.setDelegate(delegate).run(
    		sender = notGovernor,
    		voting_powers = Addresses.VOTING_POWERS,
    		valid = False
    	)

    @sp.add_test(name="setDelegate - updates delegate")
    def test():
    	# GIVEN a LiquidityFund contract without a delegate and a governor.
    	scenario = sp.test_scenario()
    	governor = Addresses.GOVERNOR_ADDRESS

    	fund = LiquidityFundContract(
    		governorContractAddress = governor
    	)
    	scenario += fund

    	# WHEN setDelegate is called by the governor
    	delegate = sp.some(Addresses.BAKER_KEY_HASH)
    	scenario += fund.setDelegate(delegate).run(
    		sender = governor,
    		voting_powers = Addresses.VOTING_POWERS
    	)

    	# THEN the delegate is updated.
    	scenario.verify(fund.baker.open_some() == delegate.open_some())

    ################################################################
    # send
    ################################################################

    @sp.add_test(name="send - succeeds when called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a LiquidityFund contract with some balance
    	balance = sp.mutez(10)
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	fund.set_initial_balance(balance)
    	scenario += fund

    	# AND a dummy contract to receive funds
    	dummyContract = DummyContract.DummyContract()
    	scenario += dummyContract

    	# WHEN send is called
    	param = (balance, dummyContract.address)
    	scenario += fund.send(param).run(
    		sender = governorContractAddress,
    	)

    	# THEN the funds are sent.
    	scenario.verify(fund.balance == sp.mutez(0))
    	scenario.verify(dummyContract.balance == balance)

    @sp.add_test(name="send - succeeds when with less than the entire amount")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a LiquidityFund contract with some balance
    	balance = sp.mutez(10)
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	fund.set_initial_balance(balance)
    	scenario += fund

    	# AND a dummy contract to receive funds
    	dummyContract = DummyContract.DummyContract()
    	scenario += dummyContract

    	# WHEN send is called with less than the full amount
    	sendAmount = sp.mutez(2)
    	param = (sendAmount, dummyContract.address)
    	scenario += fund.send(param).run(
    		sender = governorContractAddress,
    	)

    	# THEN the funds are sent.
    	scenario.verify(fund.balance == (balance - sendAmount))
    	scenario.verify(dummyContract.balance == sendAmount)        

    @sp.add_test(name="send - fails when not called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a LiquidityFund contract
    	balance = sp.mutez(10)
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	fund.set_initial_balance(balance)
    	scenario += fund

    	# WHEN send is called by someone who isn't the governor THEN the call fails
    	notGovernor = Addresses.NULL_ADDRESS
    	param = (balance, notGovernor)
    	scenario += fund.send(param).run(
    		sender = notGovernor,
    		valid = False,
    		exception = Errors.NOT_GOVERNOR
    	)    

    ################################################################
    # sendAll
    ################################################################

    @sp.add_test(name="sendAll - succeeds when called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a LiquidityFund contract with some balance
    	balance = sp.mutez(10)
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	fund.set_initial_balance(balance)
    	scenario += fund

    	# AND a dummy contract to receive funds
    	dummyContract = DummyContract.DummyContract()
    	scenario += dummyContract

    	# WHEN sendAll is called
    	scenario += fund.sendAll(dummyContract.address).run(
    		sender = governorContractAddress,
    	)

    	# THEN the funds are sent.
    	scenario.verify(fund.balance == sp.mutez(0))
    	scenario.verify(dummyContract.balance == balance)
     
    @sp.add_test(name="sendAll - fails when not called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a LiquidityFund contract
    	balance = sp.mutez(10)
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	fund.set_initial_balance(balance)
    	scenario += fund

    	# WHEN send is called by someone who isn't the governor THEN the call fails
    	notGovernor = Addresses.NULL_ADDRESS
    	scenario += fund.sendAll(notGovernor).run(
    		sender = notGovernor,
    		valid = False,
    		exception = Errors.NOT_GOVERNOR
    	)    

    ################################################################
    # sendTokens
    ################################################################

    @sp.add_test(name="sendTokens - succeeds when called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract.
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address
    	)
    	scenario += fund

    	# And a dummy contract to send to.
    	dummyContract = DummyContract.DummyContract()
    	scenario += dummyContract

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendTokens is called
    	amount = sp.nat(200)
    	param = (amount, dummyContract.address)
    	scenario += fund.sendTokens(param).run(
    		sender = governorAddress,
    	)

    	# THEN the fund is debited tokens
    	scenario.verify(token.data.balances[fund.address].balance == sp.as_nat(fundTokens - amount))

    	# AND the receiver was credited the tokens.
    	scenario.verify(token.data.balances[dummyContract.address].balance == amount)

    @sp.add_test(name="sendTokens - fails when not called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract.
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address
    	)
    	scenario += fund

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendTokens is called by someone who isn't the governor THEN the call fails.
    	notGovernor = Addresses.NULL_ADDRESS
    	amount = sp.nat(200)
    	param = (amount, Addresses.ROTATED_ADDRESS)
    	scenario += fund.sendTokens(param).run(
    		sender = notGovernor,
    		valid = False
    	)

    ################################################################
    # setGovernorContract
    ################################################################

    @sp.add_test(name="setGovernorContract - succeeds when called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setGovernorContract is called with a new contract
    	rotatedAddress = Addresses.ROTATED_ADDRESS
    	scenario += fund.setGovernorContract(rotatedAddress).run(
    		sender = governorContractAddress,
    	)

    	# THEN the contract is updated.
    	scenario.verify(fund.data.governorContractAddress == rotatedAddress)

    @sp.add_test(name="setGovernorContract - fails when not called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setGovernorContract is called by someone who isn't the governor THEN the call fails
    	rotatedAddress = Addresses.ROTATED_ADDRESS
    	scenario += fund.setGovernorContract(rotatedAddress).run(
    		sender = Addresses.NULL_ADDRESS,
    		valid = False
    	)    

    ################################################################
    # setExecutorContract
    ################################################################

    @sp.add_test(name="setExecutorContract - succeeds when called by governor")
    def test():
    	# GIVEN an LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setExecutorContract is called with a new contract
    	rotatedAddress= Addresses.ROTATED_ADDRESS
    	scenario += fund.setExecutorContract(rotatedAddress).run(
    		sender = governorContractAddress,
    	)

    	# THEN the contract is updated.
    	scenario.verify(fund.data.executorContractAddress == rotatedAddress)

    @sp.add_test(name="setExecutorContract - fails when not called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setExecutorContract is called by someone who isn't the governor THEN the call fails
    	rotatedAddress = Addresses.ROTATED_ADDRESS
    	scenario += fund.setExecutorContract(rotatedAddress).run(
    		sender = Addresses.NULL_ADDRESS,
    		valid = False
    	)    
    ################################################################
    # setSlippageTolerance
    ################################################################

    @sp.add_test(name="setSlippageTolerance - succeeds when called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setSlippageTolerance is called with some number
        someNumber = 8
    	scenario += fund.setSlippageTolerance(someNumber).run(
    		sender = governorContractAddress,
    	)

    	# THEN the contract is updated.
    	scenario.verify(fund.data.slippageTolerance == someNumber)

    @sp.add_test(name="setSlippageTolerance - fails when not called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setSlippageTolerance is called by someone who isn't the governor THEN the call fails
    	someNumber = 8
    	scenario += fund.setSlippageTolerance(someNumber).run(
    		sender = Addresses.NULL_ADDRESS,
    		valid = False
    	)    

    ################################################################
    # setMaxDataDelaySec
    ################################################################

    @sp.add_test(name="setMaxDataDelaySec - succeeds when called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN setMaxDataDelaySec is called with some number
        someNumber = 8
    	scenario += fund.setMaxDataDelaySec(someNumber).run(
    		sender = governorContractAddress,
    	)

    	# THEN the contract is updated.
    	scenario.verify(fund.data.maxDataDelaySec == someNumber)

    @sp.add_test(name="setMaxDataDelaySec - fails when not called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setMaxDataDelaySec is called by someone who isn't the governor THEN the call fails
    	someNumber = 8
    	scenario += fund.setMaxDataDelaySec(someNumber).run(
    		sender = Addresses.NULL_ADDRESS,
    		valid = False
    	)  

    ################################################################
    # setHarbingerContract
    ################################################################

    @sp.add_test(name="setHarbingerContract - succeeds when called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN setHarbingerContract is called with some address
        rotatedAddress = Addresses.ROTATED_ADDRESS
    	scenario += fund.setHarbingerContract(rotatedAddress).run(
    		sender = governorContractAddress,
    	)

    	# THEN the contract is updated.
    	scenario.verify(fund.data.harbingerContractAddress == rotatedAddress)

    @sp.add_test(name="setHarbingerContract - fails when not called by governor")
    def test():
    	# GIVEN a LiquidityFund contract
    	scenario = sp.test_scenario()

    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# WHEN the setHarbingerContract is called by someone who isn't the governor THEN the call fails
    	rotatedAddress = Addresses.ROTATED_ADDRESS
    	scenario += fund.setHarbingerContract(rotatedAddress).run(
    		sender = Addresses.NULL_ADDRESS,
    		valid = False
    	)  
    ################################################################
    # rescueFA2
    ################################################################

    @sp.add_test(name="rescueFA2 - rescues tokens")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN an FA2 token contract
    	config = FA2.FA2_config()
    	token = FA2.FA2(
    		config = config,
    		metadata = sp.utils.metadata_of_url("https://example.com"),      
    		admin = Addresses.GOVERNOR_ADDRESS
    	)
    	scenario += token

    	# AND a liquidity fund contract
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# AND the liquidity fund has tokens given to it.
    	value = sp.nat(100)
    	tokenId = 0
    	scenario += token.mint(    
    		address = fund.address,
    		amount = value,
    		metadata = FA2.FA2.make_metadata(
    			name = "SomeToken",
    			decimals = 18,
    			symbol= "ST"
    		),
    		token_id = tokenId
    	).run(
    		sender = Addresses.GOVERNOR_ADDRESS
    	)
        
    	# WHEN rescueFA2 is called.
    	scenario += fund.rescueFA2(
    		sp.record(
    			destination = Addresses.ALICE_ADDRESS,
    			amount = value,
    			tokenId = tokenId,
    			tokenContractAddress = token.address
    		)
    	).run(
    		sender = Addresses.GOVERNOR_ADDRESS,
    	)    

    	# THEN the tokens are rescued.
    	scenario.verify(token.data.ledger[(fund.address, tokenId)].balance == sp.nat(0))
    	scenario.verify(token.data.ledger[(Addresses.ALICE_ADDRESS, tokenId)].balance == value)

    @sp.add_test(name="rescueFA2 - fails if not called by govenror")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN an FA2 token contract
    	config = FA2.FA2_config()
    	token = FA2.FA2(
    		config = config,
    		metadata = sp.utils.metadata_of_url("https://example.com"),      
    		admin = Addresses.GOVERNOR_ADDRESS
    	)
    	scenario += token


    	# AND a liquidity fund contract
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# AND the liquidity fund has tokens given to it.
    	value = sp.nat(100)
    	tokenId = 0
    	scenario += token.mint(    
    		address = fund.address,
    		amount = value,
    		metadata = FA2.FA2.make_metadata(
    			name = "SomeToken",
    			decimals = 18,
    			symbol= "ST"
    		),
    		token_id = tokenId
    	).run(
    		sender = Addresses.GOVERNOR_ADDRESS
    	)
        
    	# WHEN rescueFA2 is called by someone other than the governor
    	# THEN the call fails
    	notGovernor = Addresses.NULL_ADDRESS
    	scenario += fund.rescueFA2(
    		sp.record(
    			destination = Addresses.ALICE_ADDRESS,
    			amount = value,
    			tokenId = tokenId,
    			tokenContractAddress = token.address
    		)
    	).run(
    		sender = notGovernor,
    		valid = False,
    		exception = Errors.NOT_GOVERNOR
    	)    

    ################################################################
    # rescueFA12
    ################################################################

    @sp.add_test(name="rescueFA12 - rescues tokens")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN an FA1.2 token contract
    	token_metadata = {
    		"decimals" : "18",
    		"name" : "SomeToken",
    		"symbol" : "ST",
    	}
    	contract_metadata = {
    		"" : "tezos-storage:data",
    	}
    	token = FA12.FA12(
    		admin = Addresses.GOVERNOR_ADDRESS,
    		token_metadata = token_metadata,
    		contract_metadata = contract_metadata,
    		config = FA12.FA12_config(use_token_metadata_offchain_view = False)
    	)
    	scenario += token

    	# AND a liquidity fund contract
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# AND the liquidity fund has tokens given to it.
    	value = sp.nat(100)
    	scenario += token.mint(
    		sp.record(
    			address = fund.address,
    			value = value
    		)
    	).run(
    		sender = Addresses.GOVERNOR_ADDRESS
    	)

    	# WHEN rescueFA12 is called
    	scenario += fund.rescueFA12(
    		sp.record(
    			destination = Addresses.ALICE_ADDRESS,
    			amount = value,
    			tokenContractAddress = token.address
    		)
    	).run(
    		sender = Addresses.GOVERNOR_ADDRESS,
    	)    

    	# THEN the tokens are rescued.
    	scenario.verify(token.data.balances[fund.address].balance == sp.nat(0))
    	scenario.verify(token.data.balances[Addresses.ALICE_ADDRESS].balance == value)

    @sp.add_test(name="rescueFA12 - fails to rescue if not called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN an FA1.2 token contract
    	token_metadata = {
    		"decimals" : "18",
    		"name" : "SomeToken",
    		"symbol" : "ST",
    	}
    	contract_metadata = {
    		"" : "tezos-storage:data",
    	}
    	token = FA12.FA12(
    		admin = Addresses.GOVERNOR_ADDRESS,
    		token_metadata = token_metadata,
    		contract_metadata = contract_metadata,
    		config = FA12.FA12_config(use_token_metadata_offchain_view = False)
    	)
    	scenario += token

    	# AND a liquidity fund contract
    	governorContractAddress = Addresses.GOVERNOR_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorContractAddress
    	)
    	scenario += fund

    	# AND the liquidity fund has tokens given to it.
    	value = sp.nat(100)
    	scenario += token.mint(
    		sp.record(
    			address = fund.address,
    			value = value
    		)
    	).run(
    		sender = Addresses.GOVERNOR_ADDRESS
    	)

    	# WHEN rescueFA12 is called by someone other than the governor.
    	# THEN the call fails
    	notGovernor = Addresses.NULL_ADDRESS
    	scenario += fund.rescueFA12(
    		sp.record(
    			destination = Addresses.ALICE_ADDRESS,
    			amount = value,
    			tokenContractAddress = token.address
    		)
    	).run(
    		sender = notGovernor,
    		valid = False,
    		exception = Errors.NOT_GOVERNOR
    	)    

    ################################################################
    # sendAllTokens
    ################################################################

    @sp.add_test(name="sendAllTokens - succeeds when called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract in the idle state
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract in the IDLE state
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address,

    		state = IDLE,
    		sendAllTokens_destination = sp.none
    	)
    	scenario += fund

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendAllTokens is called
    	destination = Addresses.ALICE_ADDRESS
    	scenario += fund.sendAllTokens(destination).run(
    		sender = governorAddress,
    	)

    	# THEN the fund is zero'ed
    	scenario.verify(token.data.balances[fund.address].balance == 0)

    	# AND the receiver was credited all of the tokens.
    	scenario.verify(token.data.balances[destination].balance == fundTokens)

    	# AND the state is reset
    	scenario.verify(fund.data.state == IDLE)
    	scenario.verify(fund.data.sendAllTokens_destination == sp.none)

    @sp.add_test(name="sendAllTokens - fails when not called by governor")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract in the idle state
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract in the IDLE state
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address,

    		state = IDLE,
    		sendAllTokens_destination = sp.none
    	)
    	scenario += fund

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendAllTokens is called by someone other than the governor
    	# THEN the call fails with NOT_GOVERNOR
    	destination = Addresses.ALICE_ADDRESS
    	notGovernor = Addresses.NULL_ADDRESS
    	scenario += fund.sendAllTokens(destination).run(
    		sender = notGovernor,

    		valid = False,
    		exception = Errors.NOT_GOVERNOR
    	)

    @sp.add_test(name="sendAllTokens - fails in bad state")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract in the idle state
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract in the WAITING_FOR_TOKEN_BALANCE state
    	destination = Addresses.ALICE_ADDRESS
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address,

    		state = WAITING_FOR_TOKEN_BALANCE,
    		sendAllTokens_destination = sp.some(destination)
    	)
    	scenario += fund

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendAllTokens is called
    	# THEN the call fails with BAD_STATE
    	scenario += fund.sendAllTokens(destination).run(
    		sender = governorAddress,

    		valid = False,
    		exception = Errors.BAD_STATE
    	) 

    ################################################################
    # sendAllTokens_callback
    ################################################################

    @sp.add_test(name="sendAllTokens_callback - sends the token balance")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract.
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract that is waiting to send a balance to Alice
    	recipientAddress = Addresses.ALICE_ADDRESS 
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address,

    		state = WAITING_FOR_TOKEN_BALANCE,
    		sendAllTokens_destination = sp.some(recipientAddress)
    	)
    	scenario += fund

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendAllTokens_callback is called by the token contract
    	scenario += fund.sendAllTokens_callback(fundTokens).run(
    		sender = token.address,
    	)

    	# THEN the fund is zero'ed
    	scenario.verify(token.data.balances[fund.address].balance == 0)

    	# AND the recipient was credited the tokens.
    	scenario.verify(token.data.balances[recipientAddress].balance == fundTokens)

    	# AND the state is reset
    	scenario.verify(fund.data.state == IDLE)
    	scenario.verify(fund.data.sendAllTokens_destination == sp.none)

    @sp.add_test(name="sendAllTokens_callback - fails if sender is not the token contract")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract.
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract that is waiting to send a balance to Alice
    	recipientAddress = Addresses.ALICE_ADDRESS 
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address,

    		state = WAITING_FOR_TOKEN_BALANCE,
    		sendAllTokens_destination = sp.some(recipientAddress)
    	)
    	scenario += fund

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendAllTokens_callback is called by someone other than the token contract
    	# THEN the call fails with BAD_SENDER
    	notToken = Addresses.NULL_ADDRESS
    	scenario += fund.sendAllTokens_callback(fundTokens).run(
    		sender = notToken,

    		valid = False,
    		exception = Errors.BAD_SENDER
    	)

    @sp.add_test(name="sendAllTokens_callback - fails in wrong state")
    def test():
    	scenario = sp.test_scenario()

    	# GIVEN a Token contract.
    	governorAddress = Addresses.GOVERNOR_ADDRESS
    	token = Token.FA12(
    		admin = governorAddress
    	)
    	scenario += token

    	# AND a LiquidityFund contract that is in the idle state
    	recipientAddress = Addresses.ALICE_ADDRESS 
    	fund = LiquidityFundContract(
    		governorContractAddress = governorAddress,
    		tokenContractAddress = token.address,

    		state = IDLE,
    		sendAllTokens_destination = sp.none
    	)
    	scenario += fund

    	# AND the fund has $1000 of tokens.
    	fundTokens = 1000 * Constants.PRECISION 
    	mintForFundParam = sp.record(address = fund.address, value = fundTokens)
    	scenario += token.mint(mintForFundParam).run(
    		sender = governorAddress
    	)

    	# WHEN sendAllTokens_callback is called by the token contract
    	# THEN the call fails with BAD_STATE
    	scenario += fund.sendAllTokens_callback(fundTokens).run(
    		sender = token.address,

    		valid = False,
    		exception = Errors.BAD_STATE
    	)          

    sp.add_compilation_target("liquidity-fund", LiquidityFundContract())
