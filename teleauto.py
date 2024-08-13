import os
from flask import Flask
from binance.client import Client as BinanceClient
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

app = Flask(__name__)

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 환경 변수에서 API 키와 시크릿 키 불러오기
BINANCE_API_KEY_1 = os.getenv('BINANCE_API_KEY_1')
BINANCE_SECRET_KEY_1 = os.getenv('BINANCE_SECRET_KEY_1')
BINANCE_API_KEY_2 = os.getenv('BINANCE_API_KEY_2')
BINANCE_SECRET_KEY_2 = os.getenv('BINANCE_SECRET_KEY_2')
BINANCE_API_KEY_3 = os.getenv('BINANCE_API_KEY_3')
BINANCE_SECRET_KEY_3 = os.getenv('BINANCE_SECRET_KEY_3')

# 자산을 소수점 둘째 자리로 포맷팅 및 1000단위 반점 추가
def format_balance(balance):
    return {k: "{:,.2f}".format(round(v, 2)) for k, v in balance.items()}

def format_usdt(value):
    return "{:,.2f}".format(value)

# Binance 현물 계좌 자산 현황 불러오기
def get_spot_balance(client):
    try:
        account_info = client.get_account()
        balances = account_info.get('balances', [])
        balance_details = {}

        for balance in balances:
            asset = balance.get('asset')
            free_amount = float(balance.get('free', 0))
            if free_amount > 0:
                balance_details[asset] = round(free_amount, 2)

        return balance_details

    except Exception as e:
        print(f"Error fetching Binance spot balance: {e}")
        return {}

# Binance USD-M 선물 계좌 자산 현황 불러오기
def get_usdm_futures_balance(client):
    try:
        futures_account_info = client.futures_account()
        assets = futures_account_info.get('assets', [])
        balance_details = {}

        for asset in assets:
            asset_name = asset.get('asset')
            wallet_balance = float(asset.get('walletBalance', 0))
            if wallet_balance > 0:
                balance_details[asset_name] = round(wallet_balance, 2)

        return balance_details

    except Exception as e:
        print(f"Error fetching Binance USD-M futures balance: {e}")
        return {}

# Binance USD-M 선물 포지션 자산 현황 불러오기
def get_usdm_futures_positions(client):
    try:
        positions_info = client.futures_position_information()
        position_details = {}

        for position in positions_info:
            symbol = position.get('symbol')
            asset = symbol.replace('USDT', '')
            unrealized_pnl = float(position.get('unRealizedProfit', 0))
            position_amt = float(position.get('positionAmt', 0))
            if position_amt != 0:
                position_details[asset] = round(unrealized_pnl, 2)

        return position_details

    except Exception as e:
        print(f"Error fetching Binance USD-M futures positions: {e}")
        return {}

# 자산을 USDT로 환산
def convert_to_usdt(client, balance_details):
    total_balance_usdt = 0.0
    converted_balances = {}

    for asset, free_amount in balance_details.items():
        if asset == 'USDT':
            converted_balances[asset] = round(free_amount, 2)
            total_balance_usdt += free_amount
        else:
            try:
                ticker = client.get_symbol_ticker(symbol=f"{asset}USDT")
                price = float(ticker['price'])
                balance_usdt = free_amount * price
                converted_balances[asset] = round(balance_usdt, 2)
                total_balance_usdt += balance_usdt
            except Exception as e:
                print(f"Error fetching price for {asset}: {e}")

    converted_balances['TOTAL'] = round(total_balance_usdt, 2)
    return converted_balances

# 전체 자산 현황 불러오기 (Binance)
def get_total_balance_binance(api_key, secret_key):
    client = BinanceClient(api_key, secret_key)

    # 현물 계좌 자산 불러오기
    spot_balance = get_spot_balance(client)

    # USD-M 선물 계좌 자산 불러오기
    usdm_futures_balance = get_usdm_futures_balance(client)

    # USD-M 선물 포지션 자산 불러오기
    usdm_futures_positions = get_usdm_futures_positions(client)

    # 전체 자산 합치기
    total_balance = {**spot_balance, **usdm_futures_balance}

    # 자산을 USDT로 환산
    converted_balance = convert_to_usdt(client, total_balance)

    # 선물 포지션의 unrealized PNL(USDT)을 추가
    total_unrealized_pnl = 0.0
    for asset, pnl in usdm_futures_positions.items():
        total_unrealized_pnl += pnl
        if asset in converted_balance:
            converted_balance[asset] += pnl
        else:
            converted_balance[asset] = pnl

    converted_balance['TOTAL'] = round(converted_balance['TOTAL'] + total_unrealized_pnl, 2)
    converted_balance['Unrealized PNL'] = round(total_unrealized_pnl, 2)

    return converted_balance

# HTML 포맷 함수
def format_message_html(balance, name):
    formatted = f"<b>{name} Balance: TOTAL: {balance['TOTAL']} (USDT)</b><br>"
    for asset, amount in balance.items():
        if asset != 'TOTAL':
            formatted += f"{asset}: {amount} (USDT)<br>"
    return formatted + "<br>"
  
@app.route('/')
def index():
    # Binance_1
    binance_1_balance = get_total_balance_binance(BINANCE_API_KEY_1, BINANCE_SECRET_KEY_1)
    # Binance_2
    binance_2_balance = get_total_balance_binance(BINANCE_API_KEY_2, BINANCE_SECRET_KEY_2)
    # Binance_3
    binance_3_balance = get_total_balance_binance(BINANCE_API_KEY_3, BINANCE_SECRET_KEY_3)

    # 전체 자산 계산
    total_usdt = (
        float(binance_1_balance['TOTAL']) +
        float(binance_2_balance['TOTAL']) +
        float(binance_3_balance['TOTAL'])
    )
    total_usdt_formatted = format_usdt(total_usdt)

    now = datetime.now(KST).strftime('%Y-%m-%d %H:%M')

    message = (
        f"<b>-----------------------<br>MY TOTAL COIN ASSET at {now}<br> Coin Total : {total_usdt_formatted} (USDT)</b><br><br>"
        f"{format_message_html(binance_1_balance, 'Binance_1')}"
        f"{format_message_html(binance_2_balance, 'Binance_2')}"
        f"{format_message_html(binance_3_balance, 'Binance_3')}"
    )
    return f"<html><body>{message}</body></html>"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
