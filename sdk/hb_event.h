/**
 * HB_EVENT — C contract for Harmony Bridge integration.
 * Implement this contract to emit events from C/C++ or flight software.
 * Schema: see schemas/hb_event.json; wire format: JSON.
 *
 * Usage:
 *   - Allocate an HB_EVENT struct, fill fields, then hb_event_serialize() to JSON.
 *   - Send JSON to transport (file, socket, Kafka producer, etc.).
 *   - Optional: consume ACTION_ACK by reading from transport and parsing JSON.
 */

#ifndef HB_EVENT_H
#define HB_EVENT_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Event types (must match schemas/hb_event.json) */
#define HB_EVENT_TYPE_DRIFT_EVENT      "DRIFT_EVENT"
#define HB_EVENT_TYPE_HEALTH_EVENT    "HEALTH_EVENT"
#define HB_EVENT_TYPE_ACTION_REQUEST  "ACTION_REQUEST"
#define HB_EVENT_TYPE_DECISION_SNAPSHOT "DECISION_SNAPSHOT"

/** Severity */
#define HB_SEVERITY_INFO    "info"
#define HB_SEVERITY_LOW     "low"
#define HB_SEVERITY_MEDIUM  "medium"
#define HB_SEVERITY_HIGH    "high"
#define HB_SEVERITY_CRITICAL "critical"

/** Status (for DRIFT_EVENT) */
#define HB_STATUS_PASS            "PASS"
#define HB_STATUS_PASS_WITH_DRIFT "PASS_WITH_DRIFT"
#define HB_STATUS_FAIL            "FAIL"

/** Opaque event (see implementation in hb_event.c). */
typedef struct HBEvent HBEvent;

/** Create/free (caller must free with hb_event_free). */
HBEvent *hb_event_create(void);
void hb_event_free(HBEvent *ev);

/** Setters (optional; used before serialize). */
void hb_event_set_type(HBEvent *ev, const char *type);
void hb_event_set_system_id(HBEvent *ev, const char *id);
void hb_event_set_status(HBEvent *ev, const char *status);
void hb_event_set_severity(HBEvent *ev, const char *severity);
void hb_event_set_confidence(HBEvent *ev, double c);
void hb_event_set_baseline_confidence(HBEvent *ev, double c);
void hb_event_set_action_allowed(HBEvent *ev, int allowed);
void hb_event_set_recommended_action(HBEvent *ev, const char *action);

/** Getters (after parse). */
const char *hb_event_get_type(const HBEvent *ev);
const char *hb_event_get_system_id(const HBEvent *ev);
const char *hb_event_get_status(const HBEvent *ev);
const char *hb_event_get_action_id(const HBEvent *ev);
int hb_event_get_action_allowed(const HBEvent *ev);

/**
 * Serialize event to JSON. Caller provides buffer and size.
 * Returns number of bytes written (excluding NUL), or negative on error.
 */
int hb_event_serialize(const HBEvent *ev, char *out, size_t size);

/**
 * Parse JSON into event. Caller allocates HBEvent (e.g. via hb_event_create).
 * Returns 0 on success, negative on error.
 */
int hb_event_parse(const char *json, HBEvent *out);

/**
 * Minimum fields for every HB_EVENT (see schemas/hb_event.json):
 *   type, timestamp (UTC ISO8601), system_id
 * Optional: severity, recommended_action, run_id, decision_id, payload.
 * For DRIFT_EVENT add: status, confidence, baseline_confidence, action_allowed, drift_metrics, report_path.
 * For ACTION_REQUEST add: action_type, action_id, confidence, action_allowed.
 */
typedef struct {
    const char *type;
    const char *timestamp;
    const char *system_id;
    const char *severity;
    const char *recommended_action;
    const char *run_id;
    const char *decision_id;
    const char *status;           /* DRIFT_EVENT */
    double      confidence;       /* 0..1 or -1 if unset */
    double      baseline_confidence;
    bool        action_allowed;
    const char *action_type;      /* ACTION_REQUEST */
    const char *action_id;
    const char *payload_json;     /* optional JSON object string */
} HBEventMinimal;

#ifdef __cplusplus
}
#endif

#endif /* HB_EVENT_H */
