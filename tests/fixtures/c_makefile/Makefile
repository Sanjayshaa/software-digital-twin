CC = gcc
CFLAGS = -Wall -O2

all: app

app: main.o utils.o
	$(CC) -o app main.o utils.o

clean:
	rm -f *.o app
