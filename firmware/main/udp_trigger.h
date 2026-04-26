#pragma once

#include <functional>

class UdpTrigger {
public:
    explicit UdpTrigger(std::function<void()> callback);
    void Start();

private:
    std::function<void()> callback_;
    static void TaskEntry(void* arg);
    void Run();
};
