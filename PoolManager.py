import requests
from web3 import Web3
from typing import List, Dict, Optional
import json
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class LiquidityPoolTracker:
    """Récupère les positions de liquidité pool pour une adresse EVM donnée"""

    def __init__(self, rpc_url: str, chain_id: int = 1, delay_between_calls: float = 0.5):
        """
        Initialise le tracker
        
        Args:
            rpc_url: URL du noeud RPC (ex: Infura, Alchemy)
            chain_id: ID de la chaîne (1=Ethereum, 137=Polygon, etc.)
            delay_between_calls: Délai en secondes entre chaque appel RPC
        """
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        self.delay = delay_between_calls
        self.last_call_time = 0

        # ABI minimal pour NonfungiblePositionManager (Uniswap V3 / ProjectX)
        self.position_manager_abi = [
            {
                "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
                "name": "positions",
                "outputs": [
                    {"internalType": "uint96", "name": "nonce", "type": "uint96"},
                    {"internalType": "address", "name": "operator", "type": "address"},
                    {"internalType": "address", "name": "token0", "type": "address"},
                    {"internalType": "address", "name": "token1", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "int24", "name": "tickLower", "type": "int24"},
                    {"internalType": "int24", "name": "tickUpper", "type": "int24"},
                    {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
                    {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
                    {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
                    {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
                    {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "owner", "type": "address"},
                    {"internalType": "uint256", "name": "index", "type": "uint256"}
                ],
                "name": "tokenOfOwnerByIndex",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]

        # ABI minimal pour ERC20 (pour récupérer decimals et symbol)
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

        # ABI minimal pour Pool
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

        # Adresses des Position Managers selon la chaîne
        self.position_managers = {
            1: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",  # Ethereum - Uniswap V3
            999: "0xeaD19AE861c29bBb2101E834922B2FEee69B9091",  # HEVM - ProejctX
            137: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",  # Polygon - Uniswap V3
            # Ajouter d'autres chaînes selon ProjectX
        }

    def _rate_limit_sleep(self):
        """Applique un délai pour respecter les rate limits"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time

        if time_since_last_call < self.delay:
            sleep_time = self.delay - time_since_last_call
            time.sleep(sleep_time)

        self.last_call_time = time.time()

    def _call_with_retry(self, func, max_retries=3, backoff_factor=2):
        """
        Appelle une fonction avec retry en cas d'erreur de rate limit
        
        Args:
            func: Fonction à appeler
            max_retries: Nombre maximum de tentatives
            backoff_factor: Facteur multiplicateur pour le délai entre tentatives
            
        Returns:
            Résultat de la fonction
        """
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
                        print(f"Rate limit atteint, attente de {wait_time:.1f}s avant nouvelle tentative...")
                        time.sleep(wait_time)
                    else:
                        raise Exception(f"Rate limit dépassé après {max_retries} tentatives")
                else:
                    raise e
        return None

    def tick_to_price(self, tick: int, decimals0: int = 18, decimals1: int = 18) -> float:
        """Convertit un tick en prix"""
        price = 1.0001 ** tick
        # Ajuster pour les décimales
        price = price * (10 ** decimals0) / (10 ** decimals1)
        return price

    def get_token_info(self, token_address: str) -> Dict:
        """
        Récupère les informations d'un token (symbol, decimals)
        
        Args:
            token_address: Adresse du token
            
        Returns:
            Dict avec symbol et decimals
        """
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
            print(f"Erreur lors de la récupération des infos du token: {e}")
            return {'symbol': 'UNKNOWN', 'decimals': 18}

    def calculate_token_amounts(self, liquidity: int, sqrt_price_x96: int,
                                tick_lower: int, tick_upper: int,
                                current_tick: int, decimals0: int, decimals1: int) -> Dict:
        """
        Calcule les montants de token0 et token1 dans une position
        
        Args:
            liquidity: Liquidité de la position
            sqrt_price_x96: Prix actuel en sqrtPriceX96
            tick_lower: Tick inférieur de la range
            tick_upper: Tick supérieur de la range
            current_tick: Tick actuel du pool
            decimals0: Décimales du token0
            decimals1: Décimales du token1
            
        Returns:
            Dict avec amount0, amount1 et leurs valeurs formatées
        """
        import math

        # Calculer sqrtPrice pour les bornes
        sqrt_price_lower = math.sqrt(1.0001 ** tick_lower) * (2 ** 96)
        sqrt_price_upper = math.sqrt(1.0001 ** tick_upper) * (2 ** 96)

        amount0 = 0
        amount1 = 0

        if current_tick < tick_lower:
            # Position entièrement en token0
            amount0 = liquidity * ((sqrt_price_upper - sqrt_price_lower) / (sqrt_price_lower * sqrt_price_upper))
        elif current_tick >= tick_upper:
            # Position entièrement en token1
            amount1 = liquidity * (sqrt_price_upper - sqrt_price_lower) / (2 ** 96)
        else:
            # Position dans le range, contient les deux tokens
            amount0 = liquidity * ((sqrt_price_upper - sqrt_price_x96) / (sqrt_price_x96 * sqrt_price_upper))
            amount1 = liquidity * (sqrt_price_x96 - sqrt_price_lower) / (2 ** 96)

        # Convertir en valeurs décimales
        amount0_decimal = amount0 / (10 ** decimals0)
        amount1_decimal = amount1 / (10 ** decimals1)

        # Calculer les pourcentages
        total_value = amount0_decimal + amount1_decimal  # Approximation si même valeur USD
        pct0 = (amount0_decimal / total_value * 100) if total_value > 0 else 0
        pct1 = (amount1_decimal / total_value * 100) if total_value > 0 else 0

        return {
            'amount0': amount0_decimal,
            'amount1': amount1_decimal,
            'percentage0': pct0,
            'percentage1': pct1
        }

    def get_pool_current_tick(self, pool_address: str) -> Optional[Dict]:
        """
        Récupère le tick actuel et le prix du pool
        
        Args:
            pool_address: Adresse du pool
            
        Returns:
            Dict avec tick, sqrtPriceX96 et prix
        """
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

            # Calculer le prix à partir de sqrtPriceX96
            price = (sqrt_price_x96 / (2**96)) ** 2

            return {
                'current_tick': current_tick,
                'sqrt_price_x96': sqrt_price_x96,
                'price': price
            }
        except Exception as e:
            print(f"Erreur lors de la récupération du tick actuel: {e}")
            return None

    def get_positions(self, wallet_address: str, position_manager_address: Optional[str] = None,
                      include_pool_info: bool = True) -> List[Dict]:
        """
        Récupère toutes les positions LP d'une adresse
        
        Args:
            wallet_address: Adresse du wallet à analyser
            position_manager_address: Adresse du position manager (optionnel)
            include_pool_info: Si True, récupère aussi les infos du pool (tick actuel, tokens)
            
        Returns:
            Liste des positions avec leurs détails
        """
        if position_manager_address is None:
            position_manager_address = self.position_managers.get(self.chain_id)
            if not position_manager_address:
                raise ValueError(f"Position manager non configuré pour chain_id {self.chain_id}")

        wallet_address = Web3.to_checksum_address(wallet_address)
        position_manager_address = Web3.to_checksum_address(position_manager_address)

        # Créer le contrat
        position_manager = self.w3.eth.contract(
            address=position_manager_address,
            abi=self.position_manager_abi
        )

        positions = []

        try:
            # Récupérer le nombre de positions
            def _get_balance():
                return position_manager.functions.balanceOf(wallet_address).call()

            balance = self._call_with_retry(_get_balance)
            print(f"Nombre de positions trouvées: {balance}")

            # Récupérer chaque position
            for i in range(balance):
                try:
                    print(f"Récupération de la position {i+1}/{balance}...")

                    # Obtenir l'ID du token (NFT)
                    def _get_token_id():
                        return position_manager.functions.tokenOfOwnerByIndex(wallet_address, i).call()

                    token_id = self._call_with_retry(_get_token_id)

                    # Récupérer les détails de la position
                    def _get_position():
                        return position_manager.functions.positions(token_id).call()

                    position_data = self._call_with_retry(_get_position)

                    liquidity = position_data[7]

                    # Ignorer les positions avec liquidité = 0
                    if liquidity == 0:
                        print(f"  Position #{token_id} ignorée (liquidité = 0)")
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

                    # Récupérer les infos des tokens et du pool si demandé
                    if include_pool_info:
                        token0_info = self.get_token_info(token0_address)
                        token1_info = self.get_token_info(token1_address)

                        position_info['token0_symbol'] = token0_info['symbol']
                        position_info['token1_symbol'] = token1_info['symbol']
                        position_info['token0_decimals'] = token0_info['decimals']
                        position_info['token1_decimals'] = token1_info['decimals']

                        # Calculer l'adresse du pool (simplifié - pourrait nécessiter la factory)
                        # Pour l'instant, on peut utiliser le pool directement si fourni
                        # Sinon on laisse None et l'utilisateur peut le fournir manuellement
                        position_info['pool_address'] = None

                    positions.append(position_info)

                except Exception as e:
                    print(f"Erreur lors de la récupération de la position {i}: {e}")
                    continue

            return positions

        except Exception as e:
            print(f"Erreur lors de la récupération des positions: {e}")
            return []

    def display_position_info(self, position: Dict, pool_address: Optional[str] = None):
        """
        Affiche les informations d'une position de manière lisible
        
        Args:
            position: Dict contenant les informations de la position
            pool_address: Adresse du pool pour récupérer le tick actuel
        """
        print(f"\n{'='*70}")
        print(f"Position NFT #{position['token_id']}")
        print(f"{'='*70}")

        # Afficher les symboles si disponibles
        if 'token0_symbol' in position and 'token1_symbol' in position:
            print(f"Pair: {position['token0_symbol']}/{position['token1_symbol']}")

        print(f"Token0: {position['token0']}")
        print(f"Token1: {position['token1']}")
        print(f"Fee Tier: {position['fee'] / 10000}%")
        print(f"\nRange de liquidité:")
        print(f"  Tick Lower: {position['tick_lower']} (Prix: {position['price_lower']:.6f})")
        print(f"  Tick Upper: {position['tick_upper']} (Prix: {position['price_upper']:.6f})")
        print(f"\nLiquidité: {position['liquidity']}")

        # Récupérer les infos du pool
        pool_info = None
        if pool_address:
            pool_info = self.get_pool_current_tick(pool_address)

        if pool_info:
            current_tick = pool_info['current_tick']
            print(f"\n{'─'*70}")
            print(f"📊 État du Pool:")
            print(f"  Tick actuel: {current_tick}")
            print(f"  Prix actuel: {pool_info['price']:.6f}")

            # Vérifier si la position est in-range
            in_range = position['tick_lower'] <= current_tick <= position['tick_upper']

            if in_range:
                print(f"  ✅ Position IN RANGE (active)")
            else:
                print(f"  ⚠️  ALERTE: Position OUT OF RANGE (inactive)")
                if current_tick < position['tick_lower']:
                    print(f"     → Prix actuel en dessous de la range (100% Token0)")
                else:
                    print(f"     → Prix actuel au dessus de la range (100% Token1)")

            # Calculer les montants de tokens si on a les infos nécessaires
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
                print(f"💰 Montants dans la position:")
                token0_sym = position.get('token0_symbol', 'Token0')
                token1_sym = position.get('token1_symbol', 'Token1')

                print(f"  {token0_sym}: {amounts['amount0']:.6f} ({amounts['percentage0']:.1f}%)")
                print(f"  {token1_sym}: {amounts['amount1']:.6f} ({amounts['percentage1']:.1f}%)")
        else:
            print(f"\n⚠️  Adresse du pool non fournie - impossible de vérifier le statut")

        print(f"{'='*70}")


# Exemple d'utilisation
if __name__ == "__main__":
    # Configuration
    RPC_URL = "https://hyperliquid-mainnet.g.alchemy.com/v2/gC8xL79TzkmWsPzt69Dp3Mkvg30bvpzN"  # Remplacer par votre clé
    WALLET_ADDRESS = "0x6af0b3433e185614f2ee8a6cdb789fe1de4ccd05" # Adresse à analyser
    CHAIN_ID = 999  # Ethereum mainnet
    DELAY = 1.0  # Délai d'1 seconde entre les appels (augmenter si nécessaire)

    # Créer le tracker avec gestion du rate limiting
    tracker = LiquidityPoolTracker(RPC_URL, CHAIN_ID, delay_between_calls=DELAY)

    print(f"Récupération des positions avec délai de {DELAY}s entre chaque appel...")

    # Récupérer les positions (avec infos des tokens)
    positions = tracker.get_positions(WALLET_ADDRESS, include_pool_info=True)

    # Dictionnaire pour stocker les adresses de pools si vous les connaissez
    # Format: {token_id: pool_address}
    pool_addresses = {
        # Exemple: 12345: "0xPoolAddress..."
    }

    # Afficher les positions
    for position in positions:
        pool_addr = pool_addresses.get(position['token_id'])
        tracker.display_position_info(position, pool_address=pool_addr)

    print(f"\n\nTotal: {len(positions)} position(s) active(s) trouvée(s)")
    print(f"\n💡 Note: Les 'tokens dus' (tokensOwed) s'accumulent uniquement quand vous")
    print(f"   collectez les fees ou retirez de la liquidité. C'est normal qu'ils soient à 0.")