/**
 * Example: send one HB_EVENT (DRIFT_EVENT) to stdout or file.
 * Build: c++ -I../../sdk send_event.cpp -L../../sdk/build -lhb_event -o send_event
 * Or with static: c++ -I../../sdk send_event.cpp ../../sdk/build/libhb_event.a -o send_event
 * Run: ./send_event
 *      ./send_event --status FAIL --system-id asset-001
 */
#include "../../sdk/hb_event.h"
#include <cstdio>
#include <cstring>
#include <iostream>

int main(int argc, char **argv) {
    const char *status = "PASS";
    const char *system_id = "asset-001";
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--status") == 0 && i + 1 < argc) status = argv[++i];
        else if (strcmp(argv[i], "--system-id") == 0 && i + 1 < argc) system_id = argv[++i];
    }
    HBEvent *ev = hb_event_create();
    if (!ev) return 1;
    hb_event_set_type(ev, "DRIFT_EVENT");
    hb_event_set_system_id(ev, system_id);
    hb_event_set_status(ev, status);
    hb_event_set_severity(ev, strcmp(status, "FAIL") == 0 ? "high" : "info");
    hb_event_set_confidence(ev, 0.92);
    hb_event_set_baseline_confidence(ev, 0.88);
    hb_event_set_action_allowed(ev, 1);
    hb_event_set_recommended_action(ev, strcmp(status, "FAIL") == 0 ? "DEGRADE" : "NONE");
    char buf[2048];
    int n = hb_event_serialize(ev, buf, sizeof(buf));
    hb_event_free(ev);
    if (n < 0) return 1;
    printf("%s\n", buf);
    return 0;
}
