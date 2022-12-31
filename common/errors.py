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

# VWAP vs input price difference is too great
SLIPPAGE = 8

# Not enough tokens to perform swap
NOT_ENOUGH_TOKENS = 9

# The sender was not the expected contract
BAD_SENDER = 10

# Error calling view on Harbinger Normalizer
VWAP_VIEW_ERROR = 11

# Error calling view on Harbinger spot
SPOT_VIEW_ERROR = 12

# Error while interacting with DEX contract
DEX_CONTRACT_ERROR = 13

# Wrong state while interacting with function
BAD_STATE = 14

# Error while calling approve on token
APPROVAL = 15

# Difference between spot and normalizer prices is too great
VOLATILITY = 16

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
