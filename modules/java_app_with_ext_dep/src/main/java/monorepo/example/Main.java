package monorepo.example;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.jsoup.Jsoup;

public final class Main {

    private Main() {
    }

    private static final Logger log = LogManager.getLogger(Main.class);

    public static void main(String[] args) {
        HttpClient client = HttpClient.newBuilder()
                                .followRedirects(HttpClient.Redirect.NEVER)
                                .build();
        HttpRequest request = HttpRequest.newBuilder()
                                  .uri(URI.create("http://info.cern.ch/"))
                                  .timeout(Duration.ofSeconds(5))
                                  .build();
        try {
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == HttpURLConnection.HTTP_OK) {
                log.info("\n+++++ HTML content +++++\n");
                log.info("{}", () -> Jsoup.parse(response.body()).wholeText());
            } else {
                log.warn("Failed to fetch the page. Status code: {}", response::statusCode);
            }
        } catch (IOException | InterruptedException exception) {
            log.error("Failed to fetch the page with exception.", exception);
        }
    }
}
