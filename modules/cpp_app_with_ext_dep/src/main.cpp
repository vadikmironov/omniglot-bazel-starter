#include <curl/curl.h>
#include <curl/easy.h>
#include <libxml/HTMLparser.h>
#include <libxml/tree.h>
#include <libxml/xmlstring.h>
#include <libxml/xpath.h>

#include <cstddef>
#include <cstdint>
#include <iostream>
#include <memory>
#include <string>

namespace {

auto write_callback(void* contents, size_t size, size_t nmemb, std::string* const userp) -> size_t {
    const size_t total_size = size * nmemb;
    userp->append(static_cast<char*>(contents), total_size);
    return total_size;
}

auto extract_body_text(const std::string& html, std::string& text) -> int {
    auto htmlDocPtr_close = [](htmlDocPtr doc) -> void { xmlFreeDoc(doc); };
    const std::unique_ptr<xmlDoc, decltype(htmlDocPtr_close)> doc{htmlReadMemory(
                                                                      html.c_str(), static_cast<int>(html.size()), nullptr, nullptr,
                                                                      HTML_PARSE_RECOVER | HTML_PARSE_NOERROR | HTML_PARSE_NOWARNING),  // NOLINT(hicpp-signed-bitwise)
                                                                  htmlDocPtr_close};
    if (!doc) {
        std::cerr << "Failed to parse HTML." << '\n';
        return -2;
    }

    auto xmlXPathContextPtr_close = [](xmlXPathContextPtr xpath_ctx) -> void { xmlXPathFreeContext(xpath_ctx); };
    const std::unique_ptr<xmlXPathContext, decltype(xmlXPathContextPtr_close)> xpath_ctx{xmlXPathNewContext(doc.get()),
                                                                                         xmlXPathContextPtr_close};
    if (!xpath_ctx) {
        std::cerr << "Failed to create XPath context." << '\n';
        return -2;
    }

    auto xmlXPathObjectPtr_close = [](xmlXPathObjectPtr xpath_obj) -> void { xmlXPathFreeObject(xpath_obj); };
    const std::unique_ptr<xmlXPathObject, decltype(xmlXPathObjectPtr_close)> xpath_body_obj{
        xmlXPathEvalExpression(reinterpret_cast<const xmlChar*>("//body"), xpath_ctx.get()),  // NOLINT(cppcoreguidelines-pro-type-reinterpret-cast)
        xmlXPathObjectPtr_close};
    if (!xpath_body_obj || xmlXPathNodeSetIsEmpty(xpath_body_obj->nodesetval)) {
        std::cerr << "Failed to find <body> tag in HTML." << '\n';
        return -2;
    }

    xmlNodePtr body_node = xpath_body_obj->nodesetval->nodeTab[0];  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
    // unlike python and rust implementations of html to text parsing, this one does not format links
    // and completely removed href attributes from the output which is irrelevant for the example
    // nature of this code, but still something to keep in mind when doing html to text in C++
    const std::unique_ptr<xmlChar> body_text{xmlNodeGetContent(body_node)};

    if (body_text) {
        text += reinterpret_cast<const char*>(body_text.get());  // NOLINT(cppcoreguidelines-pro-type-reinterpret-cast)
    }
    return 0;
}

}  // namespace

// Based on https://curl.se/libcurl/c/http-post.html
auto main() -> int {
    CURL* curl = nullptr;
    CURLcode res = CURLE_FAILED_INIT;
    int retval = 0;

    curl_global_init(CURL_GLOBAL_ALL);  // NOLINT(hicpp-signed-bitwise)
    curl = curl_easy_init();
    if (curl != nullptr) {
        std::string buffer;

        // NOLINTBEGIN(cppcoreguidelines-pro-type-vararg,hicpp-vararg)
        curl_easy_setopt(curl, CURLOPT_URL, "http://info.cern.ch/");
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buffer);
        // NOLINTEND(cppcoreguidelines-pro-type-vararg,hicpp-vararg)
        res = curl_easy_perform(curl);
        if (res != CURLE_OK) {
            std::cerr << "curl_easy_perform() failed: " << curl_easy_strerror(res) << '\n';
            retval = -1;
        } else {
            int64_t http_code = 0;
            curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);  // NOLINT(cppcoreguidelines-pro-type-vararg,hicpp-vararg)

            std::cout << "HTTP status code = " << http_code << '\n';

            std::cout << "\n+++++ HTML content +++++" << '\n';

            std::string text;
            retval = extract_body_text(buffer, text);
            if (retval == 0) {
                std::cout << text << '\n';
            }
        }
        curl_easy_cleanup(curl);
    } else {
        std::cerr << "Failed to initialize libcurl." << '\n';
        retval = -1;
    }

    return retval;
}
