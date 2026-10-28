news = Account(2, 'Isha')
x.transfer_to(news, 120)
try:
    news.transfer_to(x, 1000)
except InsufficientFunds as box_item:
    print('Error:', box_item)
print(x)
print(news)
import sys
