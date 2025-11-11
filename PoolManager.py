from web3 import Web3
from typing import List, Dict, Optional
import time
from dotenv import load_dotenv
import os

load_dotenv()

class LiquidityPoolTracker:

    def __init__(self, rpc_url: str, chain_id: int = 1, delay_between_calls: float = 0.5):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        self.delay = delay_between_calls
        self.last_call_time = 0

        self.position_manager_abi = [{"inputs":[{"internalType":"address","name":"_factory","type":"address"},{"internalType":"address","name":"_WETH9","type":"address"},{"internalType":"address","name":"_tokenDescriptor_","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"owner","type":"address"},{"indexed":True,"internalType":"address","name":"approved","type":"address"},{"indexed":True,"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"Approval","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"owner","type":"address"},{"indexed":True,"internalType":"address","name":"operator","type":"address"},{"indexed":False,"internalType":"bool","name":"approved","type":"bool"}],"name":"ApprovalForAll","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"uint256","name":"tokenId","type":"uint256"},{"indexed":False,"internalType":"address","name":"recipient","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"amount1","type":"uint256"}],"name":"Collect","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"uint256","name":"tokenId","type":"uint256"},{"indexed":False,"internalType":"uint128","name":"liquidity","type":"uint128"},{"indexed":False,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"amount1","type":"uint256"}],"name":"DecreaseLiquidity","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"uint256","name":"tokenId","type":"uint256"},{"indexed":False,"internalType":"uint128","name":"liquidity","type":"uint128"},{"indexed":False,"internalType":"uint256","name":"amount0","type":"uint256"},{"indexed":False,"internalType":"uint256","name":"amount1","type":"uint256"}],"name":"IncreaseLiquidity","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"from","type":"address"},{"indexed":True,"internalType":"address","name":"to","type":"address"},{"indexed":True,"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"Transfer","type":"event"},{"inputs":[],"name":"DOMAIN_SEPARATOR","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"PERMIT_TYPEHASH","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"WETH9","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"approve","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"baseURI","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"pure","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"burn","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint128","name":"amount0Max","type":"uint128"},{"internalType":"uint128","name":"amount1Max","type":"uint128"}],"internalType":"struct INonfungiblePositionManager.CollectParams","name":"params","type":"tuple"}],"name":"collect","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"}],"name":"createAndInitializePoolIfNecessary","outputs":[{"internalType":"address","name":"pool","type":"address"}],"stateMutability":"payable","type":"function"},{"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"internalType":"struct INonfungiblePositionManager.DecreaseLiquidityParams","name":"params","type":"tuple"}],"name":"decreaseLiquidity","outputs":[{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"factory","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"getApproved","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"components":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint256","name":"amount0Desired","type":"uint256"},{"internalType":"uint256","name":"amount1Desired","type":"uint256"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"internalType":"struct INonfungiblePositionManager.IncreaseLiquidityParams","name":"params","type":"tuple"}],"name":"increaseLiquidity","outputs":[{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"operator","type":"address"}],"name":"isApprovedForAll","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"components":[{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint256","name":"amount0Desired","type":"uint256"},{"internalType":"uint256","name":"amount1Desired","type":"uint256"},{"internalType":"uint256","name":"amount0Min","type":"uint256"},{"internalType":"uint256","name":"amount1Min","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"internalType":"struct INonfungiblePositionManager.MintParams","name":"params","type":"tuple"}],"name":"mint","outputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"amount0","type":"uint256"},{"internalType":"uint256","name":"amount1","type":"uint256"}],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"bytes[]","name":"data","type":"bytes[]"}],"name":"multicall","outputs":[{"internalType":"bytes[]","name":"results","type":"bytes[]"}],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"name","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"permit","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"refundETH","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"safeTransferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"},{"internalType":"bytes","name":"_data","type":"bytes"}],"name":"safeTransferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermit","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"uint256","name":"expiry","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermitAllowed","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"nonce","type":"uint256"},{"internalType":"uint256","name":"expiry","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermitAllowedIfNecessary","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"value","type":"uint256"},{"internalType":"uint256","name":"deadline","type":"uint256"},{"internalType":"uint8","name":"v","type":"uint8"},{"internalType":"bytes32","name":"r","type":"bytes32"},{"internalType":"bytes32","name":"s","type":"bytes32"}],"name":"selfPermitIfNecessary","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[{"internalType":"address","name":"operator","type":"address"},{"internalType":"bool","name":"approved","type":"bool"}],"name":"setApprovalForAll","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"bytes4","name":"interfaceId","type":"bytes4"}],"name":"supportsInterface","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"amountMinimum","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"}],"name":"sweepToken","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"tokenURI","outputs":[{"internalType":"string","name":"","type":"string"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"transferFrom","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amount0Owed","type":"uint256"},{"internalType":"uint256","name":"amount1Owed","type":"uint256"},{"internalType":"bytes","name":"data","type":"bytes"}],"name":"uniswapV3MintCallback","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"uint256","name":"amountMinimum","type":"uint256"},{"internalType":"address","name":"recipient","type":"address"}],"name":"unwrapWETH9","outputs":[],"stateMutability":"payable","type":"function"},{"stateMutability":"payable","type":"receive"}]

        self.erc20_abi = [
            {
                "inputs": [],
                "name": "decimals",
                "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "symbol",
                "outputs": [{"internalType": "string", "name": "", "type": "string"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        self.pool_abi = [
            {
                "inputs": [],
                "name": "slot0",
                "outputs": [
                    {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                    {"internalType": "int24", "name": "tick", "type": "int24"},
                    {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
                    {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
                    {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
                    {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
                    {"internalType": "bool", "name": "unlocked", "type": "bool"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        self.factory_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenA", "type": "address"},
                    {"internalType": "address", "name": "tokenB", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"}
                ],
                "name": "getPool",
                "outputs": [{"internalType": "address", "name": "pool", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        self.position_managers = {
            999: "0xeaD19AE861c29bBb2101E834922B2FEee69B9091",  # Hyperliquid EVM - ProjectX
        }

        self.factories = {
            999: "0xFf7B3e8C00e57ea31477c32A5B52a58Eea47b072",  # Hyperliquid EVM - ProjectX
        }

    def _rate_limit_sleep(self):
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time

        if time_since_last_call < self.delay:
            sleep_time = self.delay - time_since_last_call
            time.sleep(sleep_time)

        self.last_call_time = time.time()

    def _call_with_retry(self, func, max_retries=3, backoff_factor=2):
        for attempt in range(max_retries):
            try:
                self._rate_limit_sleep()
                result = func()
                return result
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (backoff_factor ** attempt) * self.delay
                        print(f"Rate limit reached, waiting {wait_time:.1f}s before retrying...")
                        time.sleep(wait_time)
                    else:
                        raise Exception(f"Rate limit exceeded after {max_retries} retry.")
                else:
                    raise e
        return None

    def tick_to_price(self, tick: int, decimals0: int = 18, decimals1: int = 18) -> float:
        price = 1.0001 ** tick
        price = price * (10 ** decimals0) / (10 ** decimals1)
        return price

    def get_token_info(self, token_address: str) -> Dict:
        try:
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.erc20_abi
            )

            def _get_symbol():
                return token_contract.functions.symbol().call()

            def _get_decimals():
                return token_contract.functions.decimals().call()

            symbol = self._call_with_retry(_get_symbol)
            decimals = self._call_with_retry(_get_decimals)

            return {'symbol': symbol, 'decimals': decimals}
        except Exception as e:
            print(f"Error while getting token infos : {e}")
            return {'symbol': 'UNKNOWN', 'decimals': 18}

    def get_pool_address(self, token0: str, token1: str, fee: int, factory_address: Optional[str] = None) -> Optional[str]:
        if factory_address is None:
            factory_address = self.factories.get(self.chain_id)
            if not factory_address:
                return None

        try:
            factory_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(factory_address),
                abi=self.factory_abi
            )

            def _get_pool():
                return factory_contract.functions.getPool(
                    Web3.to_checksum_address(token0),
                    Web3.to_checksum_address(token1),
                    fee
                ).call()

            pool_address = self._call_with_retry(_get_pool)

            if pool_address == "0x0000000000000000000000000000000000000000":
                return None

            return pool_address
        except Exception as e:
            print(f"Error while getting pool address : {e}")
            return None

    def calculate_token_amounts(self, liquidity: int, sqrt_price_x96: int,
                                tick_lower: int, tick_upper: int,
                                current_tick: int, decimals0: int, decimals1: int) -> Dict:
        import math

        sqrt_price_a = math.sqrt(1.0001 ** tick_lower)
        sqrt_price_b = math.sqrt(1.0001 ** tick_upper)
        sqrt_price_current = sqrt_price_x96 / (2 ** 96)

        amount0 = 0
        amount1 = 0

        if current_tick < tick_lower:
            # All position in token0
            amount0 = liquidity * (1 / sqrt_price_a - 1 / sqrt_price_b)
        elif current_tick >= tick_upper:
            # All position in token1
            amount1 = liquidity * (sqrt_price_b - sqrt_price_a)
        else:
            # Position in range
            amount0 = liquidity * (1 / sqrt_price_current - 1 / sqrt_price_b)
            amount1 = liquidity * (sqrt_price_current - sqrt_price_a)

        amount0_decimal = amount0 / (10 ** decimals0)
        amount1_decimal = amount1 / (10 ** decimals1)

        current_price = sqrt_price_current ** 2

        price_adjusted = current_price * (10 ** decimals0) / (10 ** decimals1)

        value0_in_token1 = amount0_decimal * price_adjusted
        value1_in_token1 = amount1_decimal

        total_value = value0_in_token1 + value1_in_token1

        pct0 = (value0_in_token1 / total_value * 100) if total_value > 0 else 0
        pct1 = (value1_in_token1 / total_value * 100) if total_value > 0 else 0

        return {
            'amount0': amount0_decimal,
            'amount1': amount1_decimal,
            'percentage0': pct0,
            'percentage1': pct1,
            'value0_in_token1': value0_in_token1,
            'value1_in_token1': value1_in_token1,
            'price': price_adjusted
        }

    def get_pool_current_tick(self, pool_address: str) -> Optional[Dict]:
        try:
            pool_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=self.pool_abi
            )

            def _call():
                return pool_contract.functions.slot0().call()

            slot0 = self._call_with_retry(_call)
            sqrt_price_x96 = slot0[0]
            current_tick = slot0[1]

            price = (sqrt_price_x96 / (2**96)) ** 2

            return {
                'current_tick': current_tick,
                'sqrt_price_x96': sqrt_price_x96,
                'price': price
            }
        except Exception as e:
            print(f"Error while getting current tick: {e}")
            return None

    def get_positions(self, wallet_address: str, position_manager_address: Optional[str] = None,
                      include_pool_info: bool = True) -> List[Dict]:
        """
        Fetch all LP positions for a given wallet address.
        
        Args:
            wallet_address: Wallet to analyze
            position_manager_address: Position manager address (optionnal)
            include_pool_info: If True, fetch pool info (token symbols, decimals, pool address)
            
        Returns:
            Detailed list of positions with relevant data
        """
        if position_manager_address is None:
            position_manager_address = self.position_managers.get(self.chain_id)
            if not position_manager_address:
                raise ValueError(f"Position manager not configured for this chain_id {self.chain_id}")

        wallet_address = Web3.to_checksum_address(wallet_address)
        position_manager_address = Web3.to_checksum_address(position_manager_address)

        position_manager = self.w3.eth.contract(
            address=position_manager_address,
            abi=self.position_manager_abi
        )

        positions = []

        try:
            def _get_balance():
                return position_manager.functions.balanceOf(wallet_address).call()

            balance = self._call_with_retry(_get_balance)
            print(f"Positions found : {balance}")

            for i in range(balance):
                try:
                    print(f"Fetching position {i+1}/{balance}...")

                    def _get_token_id():
                        return position_manager.functions.tokenOfOwnerByIndex(wallet_address, i).call()

                    token_id = self._call_with_retry(_get_token_id)

                    def _get_position():
                        return position_manager.functions.positions(token_id).call()

                    position_data = self._call_with_retry(_get_position)

                    liquidity = position_data[7]

                    if liquidity == 0:
                        print(f"  Position #{token_id} ignored (liquidity = 0)")
                        continue

                    token0_address = position_data[2]
                    token1_address = position_data[3]
                    tick_lower = position_data[5]
                    tick_upper = position_data[6]

                    position_info = {
                        'token_id': token_id,
                        'token0': token0_address,
                        'token1': token1_address,
                        'fee': position_data[4],
                        'tick_lower': tick_lower,
                        'tick_upper': tick_upper,
                        'liquidity': liquidity,
                        'price_lower': self.tick_to_price(tick_lower),
                        'price_upper': self.tick_to_price(tick_upper)
                    }

                    if include_pool_info:
                        token0_info = self.get_token_info(token0_address)
                        token1_info = self.get_token_info(token1_address)

                        position_info['token0_symbol'] = token0_info['symbol']
                        position_info['token1_symbol'] = token1_info['symbol']
                        position_info['token0_decimals'] = token0_info['decimals']
                        position_info['token1_decimals'] = token1_info['decimals']

                        pool_address = self.get_pool_address(
                            token0_address,
                            token1_address,
                            position_data[4]  # fee
                        )
                        position_info['pool_address'] = pool_address

                    positions.append(position_info)

                except Exception as e:
                    print(f"Error while fetching position {i}: {e}")
                    continue

            return positions

        except Exception as e:
            print(f"Error while fetching positions: {e}")
            return []

    def display_position_info(self, position: Dict, pool_address: Optional[str] = None):
        """
        Display detailed information about a given position.
        
        Args:
            position: Position data dictionary
            pool_address: Pool address (optional, will use position's pool address if not provided)
        """
        print(f"\n{'='*70}")
        print(f"Position NFT #{position['token_id']}")
        print(f"{'='*70}")

        if 'token0_symbol' in position and 'token1_symbol' in position:
            print(f"Pair: {position['token0_symbol']}/{position['token1_symbol']}")

        print(f"Token0: {position['token0']}")
        print(f"Token1: {position['token1']}")
        print(f"Fee Tier: {position['fee'] / 10000}%")
        print(f"\nLiquidity range :")
        print(f"  Tick Lower: {position['tick_lower']} (Price: {position['price_lower']:.6f})")
        print(f"  Tick Upper: {position['tick_upper']} (Price: {position['price_upper']:.6f})")
        print(f"\nLiquidity: {position['liquidity']}")

        if pool_address is None and 'pool_address' in position:
            pool_address = position['pool_address']

        pool_info = None
        if pool_address:
            pool_info = self.get_pool_current_tick(pool_address)

        if pool_info:
            current_tick = pool_info['current_tick']
            print(f"\n{'─'*70}")
            print(f"📊 Pool state:")
            print(f"  Adress: {pool_address}")
            print(f"  Current tick: {current_tick}")
            print(f"  Current price: {pool_info['price']:.6f}")

            in_range = position['tick_lower'] <= current_tick <= position['tick_upper']

            if in_range:
                print(f"  ✅ Position IN RANGE (active)")
            else:
                print(f"  ⚠️  ALERT: Position OUT OF RANGE (inactive)")
                if current_tick < position['tick_lower']:
                    print(f"     → Actual price below the range (100% Token0)")
                else:
                    print(f"     → Acutal price above the range (100% Token1)")

            if 'token0_decimals' in position and 'token1_decimals' in position:
                amounts = self.calculate_token_amounts(
                    position['liquidity'],
                    pool_info['sqrt_price_x96'],
                    position['tick_lower'],
                    position['tick_upper'],
                    current_tick,
                    position['token0_decimals'],
                    position['token1_decimals']
                )

                print(f"\n{'─'*70}")
                print(f"💰 Amount of tokens in the position:")
                token0_sym = position.get('token0_symbol', 'Token0')
                token1_sym = position.get('token1_symbol', 'Token1')

                print(f"  {token0_sym}: {amounts['amount0']:.6f} ({amounts['percentage0']:.1f}%)")
                print(f"  {token1_sym}: {amounts['amount1']:.6f} ({amounts['percentage1']:.1f}%)")
        else:
            print(f"\n⚠️  Cannot get pool info for address: {pool_address}")

        print(f"{'='*70}")


if __name__ == "__main__":
    RPC_URL = os.getenv('RPC_URL')
    WALLET_ADDRESS = os.getenv('WALLET_ADDRESS')
    CHAIN_ID = int(os.getenv('CHAIN_ID', '999'))
    DELAY = float(os.getenv('DELAY'))

    if not RPC_URL:
        print("❌ Error: RPC_URL not defined in .env")
        exit(1)

    tracker = LiquidityPoolTracker(RPC_URL, CHAIN_ID, delay_between_calls=DELAY)

    print(f"Fetching positions with {DELAY}s dealy between calls.")
    print(f"Wallet: {WALLET_ADDRESS}")
    print(f"Position Manager: {tracker.position_managers[CHAIN_ID]}")
    print(f"Factory: {tracker.factories[CHAIN_ID]}\n")

    positions = tracker.get_positions(WALLET_ADDRESS, include_pool_info=True)

    for position in positions:
        tracker.display_position_info(position)

    print(f"\n\nTotal: {len(positions)} active positions found.")