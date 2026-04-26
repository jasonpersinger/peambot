#include "udp_trigger.h"

#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#define TAG "UdpTrigger"
#define UDP_PORT 9999
#define WAKE_PAYLOAD "PEAMBOT_WAKE"
#define WAKE_PAYLOAD_LEN 12
#define COOLDOWN_MS 3000

UdpTrigger::UdpTrigger(std::function<void()> callback)
    : callback_(std::move(callback)) {}

void UdpTrigger::Start() {
    xTaskCreate(TaskEntry, "udp_trigger", 4096, this, 5, nullptr);
}

void UdpTrigger::TaskEntry(void* arg) {
    static_cast<UdpTrigger*>(arg)->Run();
    vTaskDelete(nullptr);
}

void UdpTrigger::Run() {
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        ESP_LOGE(TAG, "socket() failed: %d", sock);
        return;
    }

    int reuse = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

    struct sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(UDP_PORT);

    if (bind(sock, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "bind() failed on port %d", UDP_PORT);
        close(sock);
        return;
    }

    ESP_LOGI(TAG, "Listening on UDP port %d", UDP_PORT);

    char buf[32];
    TickType_t last_trigger = 0;

    while (true) {
        struct sockaddr_in sender = {};
        socklen_t sender_len = sizeof(sender);
        int len = recvfrom(sock, buf, sizeof(buf) - 1, 0,
                           (struct sockaddr*)&sender, &sender_len);
        if (len < 0) {
            ESP_LOGW(TAG, "recvfrom() error %d", len);
            continue;
        }
        if (len != WAKE_PAYLOAD_LEN || memcmp(buf, WAKE_PAYLOAD, WAKE_PAYLOAD_LEN) != 0) {
            continue;
        }
        TickType_t now = xTaskGetTickCount();
        if ((now - last_trigger) * portTICK_PERIOD_MS < COOLDOWN_MS) {
            ESP_LOGD(TAG, "Cooldown active, ignoring trigger");
            continue;
        }
        last_trigger = now;
        ESP_LOGI(TAG, "Wake trigger received from %s", inet_ntoa(sender.sin_addr));
        if (callback_) {
            callback_();
        }
    }
}
