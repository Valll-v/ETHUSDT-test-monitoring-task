import asyncio
import websockets
import json
import time
import numpy as np
from loguru import logger


'''
Код не совсем идеальный конечно, но постарался тут показать знания базовых аналитических алгоритмов + асинхронности
До работы с сокетом додумался сразу, с работой с апи также проблем не возникло, хотя и готовых инструментов не нашел 
Знаю про существование библиотеки binance, решил все же пойти по пути обычного asyncio
Писал на компиляторе CPython, поэтому полноценную многопоточность для параллельного получения результата после 
первого часа реализовать не получилось.
Получил хороший опыт с API Binance, дополнительный раз попрактиковался с асинхронностью.
Надеюсь получить его еще больше в будущем!
'''

TIME = 3_600_000  # Время, за которое (или меньше по началу) работает программа


class BinanceWSConsumer:
    async def connect(self, url):
        self.websocket = await websockets.connect(url)  # нужен отдельный метод для того, чтобы
        # не реконнектиться постоянно. Иначе по 5 секунд ожидание нового результата.
        #  можно было и без класса обойтись, но выбрал такой способ

    async def receive(self):
        while not hasattr(self, 'websocket'):  # Выглядит странно), но ничего лучше не нашел. Иначе при первом
            # ожидании подключения может произойти recv до подключения. Наверное, были и другие способы,
            # на то мы и обучаемся
            pass
        data = json.loads(await self.websocket.recv())
        price = data['c']
        timestamp = data.get('E', time.time())
        return float(price), timestamp


async def main():
    eth_prices = []
    btc_prices = []
    bwsc1 = BinanceWSConsumer()
    bwsc2 = BinanceWSConsumer()
    await bwsc1.connect('wss://fstream.binance.com/ws/ethusdt@ticker')  # Ссылка на подключение мониторинга цены
    # фьючерсов (fstream, stream при работе с настоящей ценой, в которой намного больше шумов)
    await bwsc2.connect('wss://fstream.binance.com/ws/btcusdt@ticker')

    while True:
        eth_price, eth_timestamp = await bwsc1.receive()  # Ожидаем обновление информации
        btc_price, btc_timestamp = await bwsc2.receive()
        eth_prices.append([eth_price, eth_timestamp])  # Добавляем инфо
        btc_prices.append([btc_price, btc_timestamp])
        print('ETHUSDT PRICE: ', eth_price, '\tETH TIMESTAMP: ', eth_timestamp, '\tBTCUSDT PRICE: ',
              btc_price, '\tBTC TIMESTAMP: ', btc_timestamp)  # Вывод информации (можно убрать, если не требуется,
        # во время тестов так и не поймал ситуацию с 1 процентов)
        current_time = round(time.time() * 1000)
        if current_time - eth_prices[0][1] > TIME:  # Если с первой в списке информации прошел час (левая часть
            #  удаляется ниже, поэтому максимальное количество в массиве как раз равно часу)
            eth_prices_np = np.array(eth_prices)
            btc_prices_np = np.array(btc_prices)  # Переводим для дальнейшей корреляции в np
            eth_returns = np.diff(eth_prices_np[:, 0]) / eth_prices_np[:-1, 0]  # Находим приращение для
            # каждого шага после первого
            btc_returns = np.diff(btc_prices_np[:, 0]) / btc_prices_np[:-1, 0]
            corr_coeff = np.corrcoef(eth_returns, btc_returns)[0, 1]  # Находим коэфициент корреляции (зависимость)
            eth_returns_no_btc = eth_returns - corr_coeff * btc_returns + 1  # Высчитываем для каждого шага
            # процент с учетом корреляции
            eth_returns_last_hour = np.prod(eth_returns_no_btc) * 100 - 100  # переводим в чистый процент
            print('Course change:', eth_returns_last_hour)
            del eth_prices[0]
            del btc_prices[0]  # Удаляем элементы, вышедшие за временной диапазон (в нашем случае в час)
            if abs(eth_returns_last_hour) > 1:
                logger.info(f'ETH price changed by {round(eth_returns_last_hour, 2)} in last hour!%')


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
