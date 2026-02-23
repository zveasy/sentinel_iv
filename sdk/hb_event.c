/**
 * HB_EVENT — C implementation: serialize/deserialize for Harmony Bridge.
 * Wire format: JSON. No external dependencies.
 * Build: cc -c hb_event.c -o hb_event.o && ar rcs libhb_event.a hb_event.o
 * Or: cc -fPIC -c hb_event.c -o hb_event.o && cc -shared -o libhb_event.so hb_event.o
 */
#include "hb_event.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define HB_JSON_BUF 4096
#define HB_STR_LEN 256

struct HBEvent {
    char type[HB_STR_LEN];
    char timestamp[HB_STR_LEN];
    char system_id[HB_STR_LEN];
    char severity[HB_STR_LEN];
    char recommended_action[HB_STR_LEN];
    char run_id[HB_STR_LEN];
    char decision_id[HB_STR_LEN];
    char status[HB_STR_LEN];
    double confidence;
    double baseline_confidence;
    int action_allowed;
    char action_type[HB_STR_LEN];
    char action_id[HB_STR_LEN];
    char payload_json[HB_JSON_BUF];
};

static void _escape_json(const char *s, char *out, size_t out_size) {
    size_t j = 0;
    for (; *s && j < out_size - 2; s++) {
        if (*s == '"' || *s == '\\') { out[j++] = '\\'; out[j++] = *s; }
        else if (*s == '\n') { out[j++] = '\\'; out[j++] = 'n'; }
        else out[j++] = *s;
    }
    out[j] = '\0';
}

static void _iso_utc_now(char *buf, size_t size) {
    time_t t = time(NULL);
    struct tm *utc = gmtime(&t);
    if (utc)
        strftime(buf, size, "%Y-%m-%dT%H:%M:%SZ", utc);
    else
        snprintf(buf, size, "1970-01-01T00:00:00Z");
}

int hb_event_serialize(const HBEvent *ev, char *out, size_t size) {
    if (!ev || !out || size < 64) return -1;
    char esc[HB_JSON_BUF];
    _escape_json(ev->system_id[0] ? ev->system_id : "unknown", esc, sizeof(esc));
    int n = snprintf(out, size,
        "{\"type\":\"%s\",\"timestamp\":\"%s\",\"system_id\":\"%s\"",
        ev->type[0] ? ev->type : "DRIFT_EVENT",
        ev->timestamp[0] ? ev->timestamp : "1970-01-01T00:00:00Z",
        esc);
    if (ev->severity[0]) { _escape_json(ev->severity, esc, sizeof(esc)); n += snprintf(out + n, size - (size_t)n, ",\"severity\":\"%s\"", esc); }
    if (ev->status[0])   { _escape_json(ev->status, esc, sizeof(esc)); n += snprintf(out + n, size - (size_t)n, ",\"status\":\"%s\"", esc); }
    if (ev->confidence >= 0) n += snprintf(out + n, size - (size_t)n, ",\"confidence\":%.4f", ev->confidence);
    if (ev->baseline_confidence >= 0) n += snprintf(out + n, size - (size_t)n, ",\"baseline_confidence\":%.4f", ev->baseline_confidence);
    n += snprintf(out + n, size - (size_t)n, ",\"action_allowed\":%s", ev->action_allowed ? "true" : "false");
    if (ev->recommended_action[0]) { _escape_json(ev->recommended_action, esc, sizeof(esc)); n += snprintf(out + n, size - (size_t)n, ",\"recommended_action\":\"%s\"", esc); }
    if (ev->run_id[0]) { _escape_json(ev->run_id, esc, sizeof(esc)); n += snprintf(out + n, size - (size_t)n, ",\"run_id\":\"%s\"", esc); }
    if (ev->action_type[0]) { _escape_json(ev->action_type, esc, sizeof(esc)); n += snprintf(out + n, size - (size_t)n, ",\"action_type\":\"%s\"", esc); }
    if (ev->action_id[0]) { _escape_json(ev->action_id, esc, sizeof(esc)); n += snprintf(out + n, size - (size_t)n, ",\"action_id\":\"%s\"", esc); }
    n += snprintf(out + n, size - (size_t)n, "}");
    return (n >= 0 && (size_t)n < size) ? n : -1;
}

int hb_event_parse(const char *json, HBEvent *out) {
    if (!json || !out) return -1;
    memset(out, 0, sizeof(HBEvent));
    out->confidence = -1;
    out->baseline_confidence = -1;
    /* Minimal parse: find "key":"value" pairs (no nested objects). */
    const char *p = json;
    char key[64], val[HB_STR_LEN];
    while (*p) {
        if (*p == '"') {
            p++;
            size_t ki = 0;
            while (*p && *p != '"' && ki < sizeof(key)-1) key[ki++] = *p++;
            key[ki] = '\0';
            if (*p == '"') p++;
            while (*p && (*p == ' ' || *p == ':')) p++;
            if (*p == '"') {
                p++;
                size_t vi = 0;
                while (*p && *p != '"' && vi < sizeof(val)-1) {
                    if (*p == '\\' && p[1]) { p++; val[vi++] = *p++; } else val[vi++] = *p++;
                }
                val[vi] = '\0';
                if (*p == '"') p++;
                if (strcmp(key, "type") == 0) strncpy(out->type, val, HB_STR_LEN-1);
                else if (strcmp(key, "timestamp") == 0) strncpy(out->timestamp, val, HB_STR_LEN-1);
                else if (strcmp(key, "system_id") == 0) strncpy(out->system_id, val, HB_STR_LEN-1);
                else if (strcmp(key, "status") == 0) strncpy(out->status, val, HB_STR_LEN-1);
                else if (strcmp(key, "action_type") == 0) strncpy(out->action_type, val, HB_STR_LEN-1);
                else if (strcmp(key, "action_id") == 0) strncpy(out->action_id, val, HB_STR_LEN-1);
                else if (strcmp(key, "action_allowed") == 0) out->action_allowed = (strcmp(val, "true") == 0);
            } else if (*p == 't' || *p == 'f') {
                /* unquoted boolean true/false */
                int is_true = (*p == 't' && p[1]=='r' && p[2]=='u' && p[3]=='e');
                int is_false = (*p == 'f' && p[1]=='a' && p[2]=='l' && p[3]=='s' && p[4]=='e');
                if (strcmp(key, "action_allowed") == 0) out->action_allowed = is_true ? 1 : (is_false ? 0 : out->action_allowed);
                while (*p && *p != ',' && *p != '}') p++;
            }
            while (*p && *p != '"' && *p != ',' && *p != '}') p++;
            continue;
        }
        p++;
    }
    return 0;
}

HBEvent *hb_event_create(void) {
    HBEvent *ev = (HBEvent *)calloc(1, sizeof(HBEvent));
    if (ev) {
        ev->confidence = -1;
        ev->baseline_confidence = -1;
        strncpy(ev->type, HB_EVENT_TYPE_DRIFT_EVENT, HB_STR_LEN-1);
        _iso_utc_now(ev->timestamp, HB_STR_LEN);
    }
    return ev;
}

void hb_event_free(HBEvent *ev) { free(ev); }

void hb_event_set_type(HBEvent *ev, const char *type) { if (ev && type) strncpy(ev->type, type, HB_STR_LEN-1); }
void hb_event_set_system_id(HBEvent *ev, const char *id) { if (ev && id) strncpy(ev->system_id, id, HB_STR_LEN-1); }
void hb_event_set_status(HBEvent *ev, const char *status) { if (ev && status) strncpy(ev->status, status, HB_STR_LEN-1); }
void hb_event_set_severity(HBEvent *ev, const char *s) { if (ev && s) strncpy(ev->severity, s, HB_STR_LEN-1); }
void hb_event_set_confidence(HBEvent *ev, double c) { if (ev) ev->confidence = c; }
void hb_event_set_baseline_confidence(HBEvent *ev, double c) { if (ev) ev->baseline_confidence = c; }
void hb_event_set_action_allowed(HBEvent *ev, int allowed) { if (ev) ev->action_allowed = allowed ? 1 : 0; }
void hb_event_set_recommended_action(HBEvent *ev, const char *a) { if (ev && a) strncpy(ev->recommended_action, a, HB_STR_LEN-1); }

const char *hb_event_get_type(const HBEvent *ev) { return ev ? ev->type : ""; }
const char *hb_event_get_system_id(const HBEvent *ev) { return ev ? ev->system_id : ""; }
const char *hb_event_get_status(const HBEvent *ev) { return ev ? ev->status : ""; }
const char *hb_event_get_action_id(const HBEvent *ev) { return ev ? ev->action_id : ""; }
int hb_event_get_action_allowed(const HBEvent *ev) { return ev ? ev->action_allowed : 0; }
