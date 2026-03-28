#include "arguments.hpp"

#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace kievan {

namespace {

void printUsage() {
    std::cout << "Usage: thinker --message <text> --output <file> "
                 "[--summary <text>] [--branch <label>] [--env <path>] "
                 "[--model <model-name>] [--iteration <n>] [--username <name>]\n";
}

}  // namespace

Arguments parseArguments(int argc, char *argv[]) {
    Arguments args;

    for (int i = 1; i < argc; ++i) {
        std::string current = argv[i];
        if (current == "--message" && i + 1 < argc) {
            args.message = argv[++i];
        } else if (current == "--summary" && i + 1 < argc) {
            args.summarizedThought = argv[++i];
        } else if (current == "--branch" && i + 1 < argc) {
            args.branchLabel = argv[++i];
        } else if (current == "--output" && i + 1 < argc) {
            args.outputPath = argv[++i];
        } else if (current == "--env" && i + 1 < argc) {
            args.envPath = argv[++i];
        } else if (current == "--model" && i + 1 < argc) {
            args.model = argv[++i];
        } else if (current == "--username" && i + 1 < argc) {
            args.username = argv[++i];
        } else if (current == "--iteration" && i + 1 < argc) {
            args.iteration = std::stoi(argv[++i]);
        } else if (current == "--help") {
            printUsage();
            std::exit(0);
        } else {
            std::ostringstream oss;
            oss << "Unknown or incomplete argument: " << current;
            throw std::invalid_argument(oss.str());
        }
    }

    if (args.message.empty()) {
        throw std::invalid_argument("Missing required argument --message");
    }
    if (args.outputPath.empty()) {
        throw std::invalid_argument("Missing required argument --output");
    }

    return args;
}

}  // namespace kievan
