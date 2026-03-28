#pragma once

#include <string>

namespace kievan {

/**
 * @brief Configuration passed from the Python caller into the C++ thinking engine.
 */
struct Arguments {
    std::string message;
    std::string summarizedThought;
    std::string branchLabel;
    std::string outputPath;
    std::string envPath;
    std::string model = "gemini-2.5-flash-lite";
    std::string username;
    int iteration = 0;
};

/**
 * @brief Parse command-line arguments and populate the Arguments struct.
 * @throws std::invalid_argument when a required argument is missing or malformed.
 */
Arguments parseArguments(int argc, char *argv[]);

}  // namespace kievan
