#include "engine.hpp"
#include <iostream>

namespace engine {
    void CoreEngine::start() {
        std::cout << "Starting native core..." << std::endl;
    }
    void CoreEngine::stop() {
        std::cout << "Stopping native core..." << std::endl;
    }
}
