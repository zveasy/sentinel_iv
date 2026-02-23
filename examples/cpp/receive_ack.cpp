/**
 * Example: read ACTION_ACK JSON from stdin and parse (e.g. from HB or WaveOS).
 * Build: c++ -I../../sdk receive_ack.cpp -L../../sdk/build -lhb_event -o receive_ack
 * Run: echo '{"type":"ACTION_ACK","action_id":"abc","status":"ok"}' | ./receive_ack
 */
#include "../../sdk/hb_event.h"
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>

int main() {
    std::string line;
    if (!std::getline(std::cin, line)) return 1;
    HBEvent *ev = hb_event_create();
    if (!ev) return 1;
    int r = hb_event_parse(line.c_str(), ev);
    if (r != 0) {
        hb_event_free(ev);
        return 1;
    }
    printf("parsed: type=%s system_id=%s action_id=%s action_allowed=%d\n",
           hb_event_get_type(ev), hb_event_get_system_id(ev), hb_event_get_action_id(ev), hb_event_get_action_allowed(ev));
    hb_event_free(ev);
    return 0;
}
