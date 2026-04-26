#include "peambot_display.h"

PeambotDisplay::PeambotDisplay(
    esp_lcd_panel_io_handle_t io, esp_lcd_panel_handle_t panel,
    int width, int height, int offset_x, int offset_y,
    bool mirror_x, bool mirror_y, bool swap_xy)
    : SpiLcdDisplay(io, panel, width, height, offset_x, offset_y,
                    mirror_x, mirror_y, swap_xy) {}

void PeambotDisplay::SetupUI() {
    SpiLcdDisplay::SetupUI();
}

void PeambotDisplay::SetEmotion(const char* emotion) {
    (void)emotion;
}

void PeambotDisplay::SetStatus(const char* status) {
    (void)status;
}

void PeambotDisplay::BuildEyes() {}

void PeambotDisplay::TransitionTo(EyeState state) {
    (void)state;
}

void PeambotDisplay::SetEyeColor(lv_color_t color) {
    (void)color;
}

void PeambotDisplay::ApplyIdle() {}
void PeambotDisplay::ApplyConnecting() {}
void PeambotDisplay::ApplyListening() {}
void PeambotDisplay::ApplyThinking() {}
void PeambotDisplay::ApplySpeaking() {}
void PeambotDisplay::ApplyError() {}
