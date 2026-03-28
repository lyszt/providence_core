#include "prompts.hpp"

#include <sstream>
#include <string>

namespace kievan::prompts {

namespace {

std::string escapeForJson(const std::string &text) {
    std::ostringstream escaped;
    for (char c : text) {
        switch (c) {
            case '\\': escaped << "\\\\"; break;
            case '"': escaped << "\\\""; break;
            case '\n': escaped << "\\n"; break;
            case '\r': escaped << "\\r"; break;
            case '\t': escaped << "\\t"; break;
            default: escaped << c; break;
        }
    }
    return escaped.str();
}

}  // namespace

std::string buildAnalysisPrompt(const Arguments &args) {
    std::ostringstream oss;
    oss << "You are an intelligent AI classifier.\n"
        << "Analyze the user's message and produce a JSON object with the following fields:\n"
        << "{\n"
        << "  \"user_enquiry\": string,\n"
        << "  \"user_name\": string,\n"
        << "  \"needs_command\": boolean,\n"
        << "  \"client_platform\": string,\n"
        << "  \"category\": string,\n"
        << "  \"steps_for_completion\": string,\n"
        << "  \"possible_setbacks\": string,\n"
        << "  \"probability_of_success\": number,\n"
        << "  \"potential_score\": number,\n"
        << "  \"date_of_request\": string (ISO 8601),\n"
        << "  \"is_done_thinking\": boolean,\n"
        << "  \"regrets_choice\": boolean\n"
        << "}\n"
        << "\"possible_setbacks\" must concisely list the primary risks, trade-offs, or downsides of the plan.\n"
        << "\"probability_of_success\" must be a float between 0.0 and 1.0 describing the likelihood this branch succeeds.\n"
        << "\"potential_score\" must be a float increment (positive or negative) to add to the cumulative potential score for the overall search.\n"
        << "Ensure at least two distinct branch possibilities are explored across the wider reasoning process.\n"
        << "Use the following context for iteration " << args.iteration << ":\n";

    if (!args.summarizedThought.empty()) {
        oss << "[LAST THOUGHT]\n" << args.summarizedThought << "\n";
    } else {
        oss << "[LAST THOUGHT]\nNone\n";
    }
    if (!args.branchLabel.empty()) {
        oss << "[BRANCH LABEL]\n" << args.branchLabel << "\n";
    } else {
        oss << "[BRANCH LABEL]\nPrimary\n";
    }
    oss << "Focus all analysis on the branch identified in [BRANCH LABEL] while keeping sibling branches distinct.\n";
    if (!args.username.empty()) {
        oss << "[USER NAME]\n" << args.username << "\n"
            << "Set the \"user_name\" field to the exact value above.\n";
    }
    oss << "[USER MESSAGE]\n" << args.message << "\n"
        << "Ensure the response is valid JSON and nothing else.";
    return oss.str();
}

std::string buildAnalysisPayload(const std::string &prompt) {
    std::ostringstream oss;
    oss << "{\n"
        << "  \"contents\": [\n"
        << "    {\n"
        << "      \"role\": \"user\",\n"
        << "      \"parts\": [\n"
        << "        {\n"
        << "          \"text\": \"" << escapeForJson(prompt) << "\"\n"
        << "        }\n"
        << "      ]\n"
        << "    }\n"
        << "  ],\n"
        << "  \"generationConfig\": {\n"
        << "    \"temperature\": 0.2,\n"
        << "    \"topP\": 0.9,\n"
        << "    \"maxOutputTokens\": 1024,\n"
        << "    \"responseMimeType\": \"application/json\"\n"
        << "  }\n"
        << "}";
    return oss.str();
}

std::string buildSummaryPrompt(const std::string &contextJson) {
    std::ostringstream oss;
    oss << "Summarize the thought process and decisions concisely in first person based on this JSON context:\n"
        << contextJson;
    return oss.str();
}

std::string buildSummaryPayload(const std::string &prompt) {
    std::ostringstream oss;
    oss << "{\n"
        << "  \"contents\": [\n"
        << "    {\n"
        << "      \"role\": \"user\",\n"
        << "      \"parts\": [\n"
        << "        {\n"
        << "          \"text\": \"" << escapeForJson(prompt) << "\"\n"
        << "        }\n"
        << "      ]\n"
        << "    }\n"
        << "  ],\n"
        << "  \"generationConfig\": {\n"
        << "    \"temperature\": 0.4,\n"
        << "    \"topP\": 0.9,\n"
        << "    \"maxOutputTokens\": 256,\n"
        << "    \"responseMimeType\": \"text/plain\"\n"
        << "  }\n"
        << "}";
    return oss.str();
}

}  // namespace kievan::prompts
