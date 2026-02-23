# C++ examples: build from this directory (examples/cpp) or from repo root: make -C examples/cpp
# Requires: sdk built first (from repo root: make -C sdk)

REPO_ROOT := ../..
SDK      := $(REPO_ROOT)/sdk
LIB      := $(SDK)/libhb_event.a
CXX      ?= c++
CXXFLAGS := -I$(REPO_ROOT) -Wall

.PHONY: all clean

all: send_event receive_ack

send_event: send_event.cpp $(LIB)
	$(CXX) $(CXXFLAGS) send_event.cpp $(LIB) -o send_event

receive_ack: receive_ack.cpp $(LIB)
	$(CXX) $(CXXFLAGS) receive_ack.cpp $(LIB) -o receive_ack

clean:
	rm -f send_event receive_ack
