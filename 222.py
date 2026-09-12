#
# name = "rose"
# country = "china"
# age =  22
# print("hi,I'm {} ,I'm form {} ,and I'm {}. ".format(age,country,age))

def fibonacci(n):
     a = 0
     b = 1
     for _ in range(n):
        yield a
        a,b = b,a + b
    return nums

for i in  fibonacci(100):
    print(i)