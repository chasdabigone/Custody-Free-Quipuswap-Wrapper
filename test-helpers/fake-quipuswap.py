import smartpy as sp

Addresses = sp.io.import_script_from_url("file:test-helpers/addresses.py")

# A contract which acts like a quipuswap pool. 
# Parameters are captured for inspection.
class FakeQuipuswapContract(sp.Contract):
    def __init__(
      self, 
    ):
        self.init(
            amountOut = sp.nat(0),
            destination = Addresses.NULL_ADDRESS,
            amountInvested = sp.nat(0),
            voteAmount = sp.nat(0),
            voteCandidate = sp.key_hash('tz1VQnqCCqX4K5sP3FNkVSNKTdCAMJDd3E1n'),
            voteAddress = Addresses.NULL_ADDRESS,
            vetoAmount = sp.nat(0),
            vetoAddress = Addresses.NULL_ADDRESS
        )

    # Update - Not implemented
    @sp.entry_point
    def update(self):
        pass

    # Fake entrypoint to make a XTZ -> token trade. captures parameters for inspection.
    @sp.entry_point
    def tezToTokenPayment(self, requestPair):
        sp.set_type(requestPair,  sp.TPair(sp.TNat, sp.TAddress))

        self.data.amountOut = sp.fst(requestPair)
        self.data.destination = sp.snd(requestPair)

    # Fake entrypoint to make a token -> XTZ trade. captures parameters for inspection.
    @sp.entry_point
    def tokenToTezPayment(self, requestPair):
        sp.set_type(requestPair,  sp.TPair(sp.TPair(sp.TNat, sp.TNat), sp.TAddress))

        self.data.amountOut = sp.snd(sp.fst(requestPair))
        self.data.destination = sp.snd(requestPair)

    
    # Fake entrypoint to invest liquidity. captures parameters for inspection.
    @sp.entry_point
    def investLiquidity(self, requestNat):
        sp.set_type(requestNat,  sp.TNat)

        self.data.amountInvested = requestNat

    # Fake entrypoint to divest liquidity. captures parameters for inspection.
    @sp.entry_point
    def divestLiquidity(self, requestPair):
        sp.set_type(requestPair,  sp.TPair(sp.TNat, sp.TAddress))

        self.data.amountOut = sp.fst(requestPair)
        self.data.destination = sp.snd(requestPair)

    # Fake entrypoint to vote. captures parameters for inspection.
    @sp.entry_point
    def vote(self, requestTup):
        sp.set_type(requestTup,  sp.TPair(sp.TPair(sp.TKeyHash, sp.TNat), sp.TAddress))

        self.data.voteAmount = sp.snd(sp.fst(requestTup))
        self.data.voteCandidate = sp.fst(sp.fst(requestTup))
        self.data.voteAddress = sp.snd(requestTup)


    # Fake entrypoint to veto. captures parameters for inspection.
    @sp.entry_point
    def veto(self, requestPair):
        sp.set_type(requestPair,  sp.TPair(sp.TNat, sp.TAddress))

        self.data.vetoAmount = sp.fst(requestPair)
        self.data.vetoAddress = sp.snd(requestPair)
