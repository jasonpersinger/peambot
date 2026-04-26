#pragma once

#include "display/lcd_display.h"
#include <lvgl.h>

enum class EyeState {
    Idle,
    Connecting,
    Listening,
    Thinking,
    Speaking,
    Error,
};

class PeambotDisplay : public SpiLcdDisplay {
public:
    PeambotDisplay(esp_lcd_panel_io_handle_t io,
                   esp_lcd_panel_handle_t panel,
                   int width, int height,
                   int offset_x, int offset_y,
                   bool mirror_x, bool mirror_y, bool swap_xy);

    void SetupUI() override;
    void SetEmotion(const char* emotion) override;
    void SetStatus(const char* status) override;

private:
    void BuildEyes();
    void TransitionTo(EyeState state);
    void SetEyeColor(lv_color_t color);
    void ApplyIdle();
    void ApplyConnecting();
    void ApplyListening();
    void ApplyThinking();
    void ApplySpeaking();
    void ApplyError();

    EyeState current_state_ = EyeState::Idle;

    lv_obj_t* left_eye_    = nullptr;
    lv_obj_t* left_iris_   = nullptr;
    lv_obj_t* left_pupil_  = nullptr;

    lv_obj_t* right_eye_   = nullptr;
    lv_obj_t* right_iris_  = nullptr;
    lv_obj_t* right_pupil_ = nullptr;
};
