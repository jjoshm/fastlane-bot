# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.5
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# coding=utf-8
"""
This module contains the tests for the exchanges classes
"""
from fastlane_bot import Bot, Config
from fastlane_bot.bot import CarbonBot
from fastlane_bot.tools.cpc import ConstantProductCurve
from fastlane_bot.tools.cpc import ConstantProductCurve as CPC
from fastlane_bot.events.exchanges import UniswapV2, UniswapV3,  CarbonV1, BancorV3
from fastlane_bot.events.interface import QueryInterface
from fastlane_bot.helpers.poolandtokens import PoolAndTokens
from fastlane_bot.helpers import TradeInstruction, TxReceiptHandler, TxRouteHandler, TxSubmitHandler, TxHelpers, TxHelper
from fastlane_bot.events.managers.manager import Manager
from fastlane_bot.events.interface import QueryInterface
from joblib import Parallel, delayed
import pytest
import math
import json
print("{0.__name__} v{0.__VERSION__} ({0.__DATE__})".format(CPC))
print("{0.__name__} v{0.__VERSION__} ({0.__DATE__})".format(Bot))
print("{0.__name__} v{0.__VERSION__} ({0.__DATE__})".format(UniswapV2))
print("{0.__name__} v{0.__VERSION__} ({0.__DATE__})".format(UniswapV3))
print("{0.__name__} v{0.__VERSION__} ({0.__DATE__})".format(CarbonV1))
print("{0.__name__} v{0.__VERSION__} ({0.__DATE__})".format(BancorV3))
from fastlane_bot.testing import *
#plt.style.use('seaborn-dark')
plt.rcParams['figure.figsize'] = [12,6]
from fastlane_bot import __VERSION__
require("3.0", __VERSION__)

# # Multi Mode [NB039]

# +
C = cfg = Config.new(config=Config.CONFIG_MAINNET)
cfg.DEFAULT_MIN_PROFIT_GAS_TOKEN = 0.00001
assert (C.NETWORK == C.NETWORK_MAINNET)
assert (C.PROVIDER == C.PROVIDER_ALCHEMY)
setup_bot = CarbonBot(ConfigObj=C)
pools = None
with open('fastlane_bot/data/tests/latest_pool_data_testing.json') as f:
    pools = json.load(f)
pools = [pool for pool in pools]
pools[0]
static_pools = pools
state = pools
exchanges = list({ex['exchange_name'] for ex in state})
db = QueryInterface(state=state, ConfigObj=C, exchanges=exchanges)
setup_bot.db = db

static_pool_data_filename = "static_pool_data"

static_pool_data = pd.read_csv(f"fastlane_bot/data/{static_pool_data_filename}.csv", low_memory=False)
    
uniswap_v2_event_mappings = pd.read_csv("fastlane_bot/data/uniswap_v2_event_mappings.csv", low_memory=False)
        
tokens = pd.read_csv("fastlane_bot/data/tokens.csv", low_memory=False)
        
exchanges = "carbon_v1,bancor_v3,uniswap_v3,uniswap_v2,sushiswap_v2"

exchanges = exchanges.split(",")


alchemy_max_block_fetch = 20
static_pool_data["cid"] = [
        cfg.w3.keccak(text=f"{row['descr']}").hex()
        for index, row in static_pool_data.iterrows()
    ]
# Filter out pools that are not in the supported exchanges
static_pool_data = [
    row for index, row in static_pool_data.iterrows()
    if row["exchange_name"] in exchanges
]

static_pool_data = pd.DataFrame(static_pool_data)
static_pool_data['exchange_name'].unique()
# Initialize data fetch manager
mgr = Manager(
    web3=cfg.w3,
    w3_async=cfg.w3_async,
    cfg=cfg,
    pool_data=static_pool_data.to_dict(orient="records"),
    SUPPORTED_EXCHANGES=exchanges,
    alchemy_max_block_fetch=alchemy_max_block_fetch,
    uniswap_v2_event_mappings=uniswap_v2_event_mappings,
    tokens=tokens.to_dict(orient="records"),
)

# Add initial pools for each row in the static_pool_data
start_time = time.time()
Parallel(n_jobs=-1, backend="threading")(
    delayed(mgr.add_pool_to_exchange)(row) for row in mgr.pool_data
)
cfg.logger.info(f"Time taken to add initial pools: {time.time() - start_time}")

# check if any duplicate cid's exist in the pool data
mgr.deduplicate_pool_data()
cids = [pool["cid"] for pool in mgr.pool_data]
assert len(cids) == len(set(cids)), "duplicate cid's exist in the pool data"
def init_bot(mgr: Manager) -> CarbonBot:
    """
    Initializes the bot.

    Parameters
    ----------
    mgr : Manager
        The manager object.

    Returns
    -------
    CarbonBot
        The bot object.
    """
    mgr.cfg.logger.info("Initializing the bot...")
    bot = CarbonBot(ConfigObj=mgr.cfg)
    bot.db = db
    bot.db.mgr = mgr
    assert isinstance(
        bot.db, QueryInterface
    ), "QueryInterface not initialized correctly"
    return bot
bot = init_bot(mgr)
# add data cleanup steps from main.py
bot.db.remove_unmapped_uniswap_v2_pools()
bot.db.remove_zero_liquidity_pools()
bot.db.remove_unsupported_exchanges()
tokens = bot.db.get_tokens()
ADDRDEC = {t.address: (t.address, int(t.decimals)) for t in tokens if not math.isnan(t.decimals)}
flashloan_tokens = bot.setup_flashloan_tokens(None)
CCm = bot.setup_CCm(None)
pools = db.get_pool_data_with_tokens()

arb_mode = "multi"
# -

# ## Test_MIN_PROFIT

assert(cfg.DEFAULT_MIN_PROFIT_GAS_TOKEN <= 0.0001), f"[TestMultiMode], default_min_profit_gas_token must be <= 0.02 for this Notebook to run, currently set to {cfg.DEFAULT_MIN_PROFIT_GAS_TOKEN}"

# ## Test_get_arb_finder

arb_finder = bot._get_arb_finder("multi")
assert arb_finder.__name__ == "FindArbitrageMultiPairwise", f"[TestMultiMode] Expected arb_finder class name name = FindArbitrageMultiPairwise, found {arb_finder.__name__}"

# ## Test_Combos_and_Tokens

# +
arb_finder = bot._get_arb_finder("multi")
finder2 = arb_finder(
            flashloan_tokens=flashloan_tokens,
            CCm=CCm,
            mode="bothin",
            result=bot.AO_TOKENS,
            ConfigObj=bot.ConfigObj,
        )
all_tokens, combos = finder2.find_arbitrage()

assert type(all_tokens) == set, f"[NBTest 039 TestMultiMode] all_tokens is wrong data type. Expected set, found: {type(all_tokens)}"
assert type(combos) == list, f"[NBTest 039 TestMultiMode] combos is wrong data type. Expected list, found: {type(combos)}"
assert len(all_tokens) >= 236, f"[NBTest 039 TestMultiMode] Using wrong dataset, expected at least 236 tokens, found {len(all_tokens)}"
assert len(combos) >= 1410, f"[NBTest 039 TestMultiMode] Using wrong dataset, expected at least 1410 combos, found {len(combos)}"
# -

# ## Test_Expected_Output

# +
arb_finder = bot._get_arb_finder("multi_pairwise_pol")
finder = arb_finder(
            flashloan_tokens=flashloan_tokens,
            CCm=CCm,
            mode="bothin",
            result=bot.AO_CANDIDATES,
            ConfigObj=bot.ConfigObj,
        )

r = finder.find_arbitrage()

multi_carbon_count = 0
carbon_wrong_direction_count = 0
for arb in r:
    (
            best_profit,
            best_trade_instructions_df,
            best_trade_instructions_dic,
            best_src_token,
            best_trade_instructions,
        ) = arb
    if len(best_trade_instructions_dic) > 2:
        multi_carbon_count += 1
        carbon_tkn_in = None
        for trade in best_trade_instructions_dic:
            if "-" in trade["cid"]:
                if carbon_tkn_in is None:
                    carbon_tkn_in = trade["tknin"]
                else:
                    if trade["tknin"] not in carbon_tkn_in:
                        carbon_wrong_direction_count += 1

assert len(r) >= 36, f"[NBTest 039 TestMultiMode] Expected at least 27 arbs, found {len(r)}"
assert multi_carbon_count > 0, f"[NBTest 039 TestMultiMode] Not finding arbs with multiple Carbon curves."
assert carbon_wrong_direction_count == 0, f"[NBTest 039 TestMultiMode] Expected all Carbon curves to have the same tkn in and tkn out. Mixing is currently not supported."
# -


