#include "peambot_display.h"
#include <esp_log.h>
#include <cstring>
#include <string_view>

static const char* TAG = "PeambotDisplay";

// ── Geometry ──────────────────────────────────────────────
static constexpr int EYE_W       = 110;
static constexpr int EYE_H       = 140;
static constexpr int IRIS_SIZE   = 74;
static constexpr int PUPIL_SIZE  = 32;
static constexpr int LEFT_EYE_X  = 50;
static constexpr int RIGHT_EYE_X = 208;
static constexpr int EYE_Y       = 154;
static constexpr int SHADOW_W    = 28;

// ── Animation callbacks ────────────────────────────────────
static void anim_height_cb(void* var, int32_t val) {
    lv_obj_set_height((lv_obj_t*)var, val);
}
static void anim_x_cb(void* var, int32_t val) {
    lv_obj_set_x((lv_obj_t*)var, val);
}
static void anim_shadow_opa_cb(void* var, int32_t val) {
    lv_obj_set_style_shadow_opa((lv_obj_t*)var, (lv_opa_t)val, 0);
}
static void anim_opa_cb(void* var, int32_t val) {
    lv_obj_set_style_opa((lv_obj_t*)var, (lv_opa_t)val, 0);
}

// ── Color per state ────────────────────────────────────────
static lv_color_t state_color(EyeState s) {
    switch (s) {
        case EyeState::Idle:       return lv_color_make(0x1e, 0x90, 0xff);
        case EyeState::Connecting: return lv_color_make(0xf0, 0xa5, 0x00);
        case EyeState::Listening:  return lv_color_make(0x00, 0xe5, 0xff);
        case EyeState::Thinking:   return lv_color_make(0x9b, 0x59, 0xf5);
        case EyeState::Speaking:   return lv_color_make(0x00, 0xd6, 0x7a);
        case EyeState::Error:      return lv_color_make(0xe0, 0x30, 0x30);
        default:                   return lv_color_make(0x1e, 0x90, 0xff);
    }
}

// ── Object factories ───────────────────────────────────────
static lv_obj_t* make_eye(lv_obj_t* parent, int x, int y) {
    lv_obj_t* eye = lv_obj_create(parent);
    lv_obj_set_size(eye, EYE_W, EYE_H);
    lv_obj_set_pos(eye, x, y);
    lv_obj_set_style_radius(eye, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(eye, lv_color_white(), 0);
    lv_obj_set_style_bg_opa(eye, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(eye, 0, 0);
    lv_obj_set_style_pad_all(eye, 0, 0);
    lv_obj_set_style_clip_corner(eye, true, 0);
    lv_obj_set_style_shadow_width(eye, SHADOW_W, 0);
    lv_obj_set_style_shadow_spread(eye, 4, 0);
    lv_obj_set_style_shadow_color(eye, lv_color_make(0x1e, 0x90, 0xff), 0);
    lv_obj_set_style_shadow_opa(eye, LV_OPA_50, 0);
    return eye;
}

static lv_obj_t* make_iris(lv_obj_t* eye, lv_color_t color) {
    lv_obj_t* iris = lv_obj_create(eye);
    lv_obj_set_size(iris, IRIS_SIZE, IRIS_SIZE);
    lv_obj_align(iris, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_radius(iris, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(iris, color, 0);
    lv_obj_set_style_bg_opa(iris, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(iris, 0, 0);
    lv_obj_set_style_pad_all(iris, 0, 0);
    return iris;
}

static lv_obj_t* make_pupil(lv_obj_t* iris) {
    lv_obj_t* pupil = lv_obj_create(iris);
    lv_obj_set_size(pupil, PUPIL_SIZE, PUPIL_SIZE);
    lv_obj_align(pupil, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_radius(pupil, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(pupil, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(pupil, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(pupil, 0, 0);
    lv_obj_set_style_pad_all(pupil, 0, 0);
    return pupil;
}

// ── Constructor ────────────────────────────────────────────
PeambotDisplay::PeambotDisplay(
    esp_lcd_panel_io_handle_t io, esp_lcd_panel_handle_t panel,
    int width, int height, int offset_x, int offset_y,
    bool mirror_x, bool mirror_y, bool swap_xy)
    : SpiLcdDisplay(io, panel, width, height, offset_x, offset_y,
                    mirror_x, mirror_y, swap_xy) {}

// ── SetupUI ────────────────────────────────────────────────
void PeambotDisplay::SetupUI() {
    SpiLcdDisplay::SetupUI();
    DisplayLockGuard lock(this);

    // Hide all default widgets
    lv_obj_t* widgets[] = {status_bar_, content_, container_, side_bar_, bottom_bar_};
    for (auto* obj : widgets) {
        if (obj) lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
    }

    lv_obj_set_style_bg_color(lv_scr_act(), lv_color_black(), 0);
    lv_obj_set_style_bg_opa(lv_scr_act(), LV_OPA_COVER, 0);

    BuildEyes();
    ApplyIdle();
}

// ── BuildEyes ─────────────────────────────────────────────
void PeambotDisplay::BuildEyes() {
    lv_color_t c = state_color(EyeState::Idle);

    left_eye_   = make_eye(lv_scr_act(), LEFT_EYE_X, EYE_Y);
    left_iris_  = make_iris(left_eye_, c);
    left_pupil_ = make_pupil(left_iris_);

    right_eye_   = make_eye(lv_scr_act(), RIGHT_EYE_X, EYE_Y);
    right_iris_  = make_iris(right_eye_, c);
    right_pupil_ = make_pupil(right_iris_);
}

// ── SetEyeColor ───────────────────────────────────────────
void PeambotDisplay::SetEyeColor(lv_color_t color) {
    lv_obj_set_style_bg_color(left_iris_, color, 0);
    lv_obj_set_style_bg_color(right_iris_, color, 0);
    lv_obj_set_style_shadow_color(left_eye_, color, 0);
    lv_obj_set_style_shadow_color(right_eye_, color, 0);
}

// ── TransitionTo ──────────────────────────────────────────
void PeambotDisplay::TransitionTo(EyeState new_state) {
    if (new_state == current_state_) return;
    current_state_ = new_state;

    lv_anim_del(left_eye_, nullptr);
    lv_anim_del(right_eye_, nullptr);

    // Reset geometry to defaults
    lv_obj_set_size(left_eye_, EYE_W, EYE_H);
    lv_obj_set_size(right_eye_, EYE_W, EYE_H);
    lv_obj_set_x(left_eye_, LEFT_EYE_X);
    lv_obj_set_x(right_eye_, RIGHT_EYE_X);
    lv_obj_align(left_iris_, LV_ALIGN_CENTER, 0, 0);
    lv_obj_align(right_iris_, LV_ALIGN_CENTER, 0, 0);
    lv_obj_set_style_shadow_width(left_eye_, SHADOW_W, 0);
    lv_obj_set_style_shadow_width(right_eye_, SHADOW_W, 0);
    lv_obj_set_style_opa(left_eye_, LV_OPA_COVER, 0);
    lv_obj_set_style_opa(right_eye_, LV_OPA_COVER, 0);

    switch (new_state) {
        case EyeState::Idle:       ApplyIdle();       break;
        case EyeState::Connecting: ApplyConnecting(); break;
        case EyeState::Listening:  ApplyListening();  break;
        case EyeState::Thinking:   ApplyThinking();   break;
        case EyeState::Speaking:   ApplySpeaking();   break;
        case EyeState::Error:      ApplyError();      break;
    }
}

// ── ApplyIdle ─────────────────────────────────────────────
void PeambotDisplay::ApplyIdle() {
    SetEyeColor(state_color(EyeState::Idle));

    lv_obj_t* eyes[2] = {left_eye_, right_eye_};
    for (int i = 0; i < 2; i++) {
        lv_anim_t a;

        // Blink: close in 120ms, open in 80ms, repeat every ~5s
        // LVGL 9.x uses lv_anim_set_reverse_duration instead of lv_anim_set_playback_time
        lv_anim_init(&a);
        lv_anim_set_var(&a, eyes[i]);
        lv_anim_set_values(&a, EYE_H, 4);
        lv_anim_set_exec_cb(&a, anim_height_cb);
        lv_anim_set_duration(&a, 120);
        lv_anim_set_reverse_duration(&a, 80);
        lv_anim_set_delay(&a, 5000 + i * 80);
        lv_anim_set_repeat_delay(&a, 4800);
        lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
        lv_anim_start(&a);

        // Glow breathe
        lv_anim_init(&a);
        lv_anim_set_var(&a, eyes[i]);
        lv_anim_set_values(&a, LV_OPA_30, LV_OPA_70);
        lv_anim_set_exec_cb(&a, anim_shadow_opa_cb);
        lv_anim_set_duration(&a, 2500);
        lv_anim_set_reverse_duration(&a, 2500);
        lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_in_out);
        lv_anim_start(&a);
    }
}

// ── ApplyConnecting — amber, scanning sweep ───────────────
void PeambotDisplay::ApplyConnecting() {
    SetEyeColor(state_color(EyeState::Connecting));

    lv_obj_t* eyes[2] = {left_eye_, right_eye_};
    int base_x[2]     = {LEFT_EYE_X, RIGHT_EYE_X};
    for (int i = 0; i < 2; i++) {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, eyes[i]);
        lv_anim_set_values(&a, base_x[i] - 18, base_x[i] + 18);
        lv_anim_set_exec_cb(&a, anim_x_cb);
        lv_anim_set_duration(&a, 1100);
        lv_anim_set_reverse_duration(&a, 1100);
        lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_in_out);
        lv_anim_start(&a);
    }
}

// ── ApplyListening — cyan, wide open, glow pulse ──────────
void PeambotDisplay::ApplyListening() {
    SetEyeColor(state_color(EyeState::Listening));

    lv_obj_t* eyes[2] = {left_eye_, right_eye_};
    for (int i = 0; i < 2; i++) {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, eyes[i]);
        lv_anim_set_values(&a, LV_OPA_50, LV_OPA_COVER);
        lv_anim_set_exec_cb(&a, anim_shadow_opa_cb);
        lv_anim_set_duration(&a, 700);
        lv_anim_set_reverse_duration(&a, 700);
        lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_in_out);
        lv_anim_start(&a);
    }
}

// ── ApplyThinking — purple, gaze up-left, slow blink ──────
void PeambotDisplay::ApplyThinking() {
    SetEyeColor(state_color(EyeState::Thinking));

    // Shift iris gaze up-left
    lv_obj_align(left_iris_,  LV_ALIGN_CENTER, -12, -14);
    lv_obj_align(right_iris_, LV_ALIGN_CENTER, -12, -14);

    lv_obj_t* eyes[2] = {left_eye_, right_eye_};
    for (int i = 0; i < 2; i++) {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, eyes[i]);
        lv_anim_set_values(&a, EYE_H, 4);
        lv_anim_set_exec_cb(&a, anim_height_cb);
        lv_anim_set_duration(&a, 120);
        lv_anim_set_reverse_duration(&a, 80);
        lv_anim_set_delay(&a, 7000 + i * 80);
        lv_anim_set_repeat_delay(&a, 6800);
        lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
        lv_anim_start(&a);
    }
}

// ── ApplySpeaking — green, rhythmic squint ────────────────
void PeambotDisplay::ApplySpeaking() {
    SetEyeColor(state_color(EyeState::Speaking));

    lv_obj_t* eyes[2] = {left_eye_, right_eye_};
    for (int i = 0; i < 2; i++) {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, eyes[i]);
        lv_anim_set_values(&a, EYE_H, 60);
        lv_anim_set_exec_cb(&a, anim_height_cb);
        lv_anim_set_duration(&a, 380);
        lv_anim_set_reverse_duration(&a, 380);
        lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
        lv_anim_set_path_cb(&a, lv_anim_path_ease_in_out);
        lv_anim_start(&a);
    }
}

// ── ApplyError — red, narrowed, flicker ───────────────────
void PeambotDisplay::ApplyError() {
    SetEyeColor(state_color(EyeState::Error));
    lv_obj_set_height(left_eye_, 80);
    lv_obj_set_height(right_eye_, 80);

    lv_obj_t* eyes[2] = {left_eye_, right_eye_};
    for (int i = 0; i < 2; i++) {
        lv_anim_t a;
        lv_anim_init(&a);
        lv_anim_set_var(&a, eyes[i]);
        lv_anim_set_values(&a, LV_OPA_COVER, LV_OPA_50);
        lv_anim_set_exec_cb(&a, anim_opa_cb);
        lv_anim_set_duration(&a, 200);
        lv_anim_set_reverse_duration(&a, 200);
        lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
        lv_anim_start(&a);
    }
}

// ── SetStatus ─────────────────────────────────────────────
void PeambotDisplay::SetStatus(const char* status) {
    if (!status || !left_eye_) return;
    DisplayLockGuard lock(this);

    std::string_view s(status);
    EyeState next = EyeState::Idle;

    if (s.find("Connecting") != std::string_view::npos ||
        s.find("Logging in") != std::string_view::npos ||
        s.find("Waiting for network") != std::string_view::npos) {
        next = EyeState::Connecting;
    } else if (s.find("Listening") != std::string_view::npos) {
        next = EyeState::Listening;
    } else if (s.find("Thinking") != std::string_view::npos) {
        next = EyeState::Thinking;
    } else if (s.find("Speaking") != std::string_view::npos) {
        next = EyeState::Speaking;
    } else if (s.find("Error") != std::string_view::npos ||
               s.find("Failed") != std::string_view::npos ||
               s.find("Timeout") != std::string_view::npos ||
               s.find("Unable") != std::string_view::npos) {
        next = EyeState::Error;
    }

    TransitionTo(next);
}

// ── SetEmotion ────────────────────────────────────────────
void PeambotDisplay::SetEmotion(const char* emotion) {
    if (!emotion || !left_eye_) return;
    DisplayLockGuard lock(this);

    std::string_view e(emotion);
    if (e == "thinking") {
        TransitionTo(EyeState::Thinking);
    } else if (e == "happy" || e == "excited") {
        TransitionTo(EyeState::Listening);
    }
    // "neutral" and unrecognised: no override
}
