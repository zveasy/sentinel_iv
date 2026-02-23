# Build libhb_event.a and libhb_event.so (no cmake required)
# Usage: make

CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra
AR ?= ar

libhb_event.a: hb_event.c hb_event.h
	$(CC) $(CFLAGS) -c hb_event.c -o hb_event.o
	$(AR) rcs libhb_event.a hb_event.o

libhb_event.so: hb_event.c hb_event.h
	$(CC) $(CFLAGS) -fPIC -c hb_event.c -o hb_event.o
	$(CC) -shared -o libhb_event.so hb_event.o

clean:
	rm -f hb_event.o libhb_event.a libhb_event.so

.PHONY: clean
