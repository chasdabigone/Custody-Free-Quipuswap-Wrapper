import smartpy as sp

# This file contains addresses for tests which are named and ensure uniqueness across the test suite.

# The address which acts as the Governor
GOVERNOR_ADDRESS = sp.address("tz1YYnf7vGXqCmB1shNg4rHiTz5gwWTDYceB")

# The address which acts as the addLiquidity Executor
EXECUTOR_ADDRESS = sp.address("tz1YYnf7vGXqCmB1shNg4rHiTz5gwWTDYceB")

# The address that acts as the token contract.
TOKEN_ADDRESS = sp.address("KT1RBR9i6R7T56DJbaUtzDNuCt9KHLM8bVpW")

# The address of a XTZ/kUSD Quipuswap contract
QUIPUSWAP_ADDRESS = sp.address("KT1VVYfncoCWrwG6Bwd4MFuq3Xj8c4ndW5qF")

# The address of the Harbinger Normalizer (views)
HARBINGER_VWAP_ADDRESS = sp.address("KT1ENe4jbDE1QVG1euryp23GsAeWuEwJutQX")

# The address of the Harbinger Spot Price (views)
HARBINGER_SPOT_ADDRESS = sp.address("KT1UcwQtaztLSq8oufdXAtWpRTfFySCj7gFM")

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
