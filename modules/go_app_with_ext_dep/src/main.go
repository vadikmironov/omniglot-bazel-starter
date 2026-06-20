package main

import (
	"bytes"
	"io"
	"log"
	"log/slog"
	"net/http"
	"strings"

	"golang.org/x/net/html"
)

func html_whole_text(r *html.Node) string {
	for r.Type != html.ElementNode {
		switch r.Type {
		case html.DocumentNode:
			r = r.FirstChild
		case html.DoctypeNode:
			r = r.NextSibling
		case html.CommentNode:
			r = r.NextSibling
		}
	}

	var buf bytes.Buffer
	var f func(*html.Node)
	f = func(n *html.Node) {
		if n == nil {
			return
		}
		if n.Type == html.TextNode {
			buf.WriteString(n.Data)
		}
		if n.Type == html.ElementNode {
			f(n.FirstChild)
		}
		if n.NextSibling != nil {
			f(n.NextSibling)
		}
	}

	f(r.FirstChild)

	return buf.String()
}

func main() {
	client := &http.Client{}
	req, err := http.NewRequest("GET", "http://info.cern.ch/", nil)
	if err != nil {
		slog.Error("Error creating request:", err)
		return
	}

	resp, err := client.Do(req)
	if err != nil {
		slog.Error("Error sending request:", err)
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		slog.Error("Error reading response:", err)
		return
	}

	r, err := html.Parse(strings.NewReader(string(body)))
	if err != nil {
		slog.Error("Unable to parse HTML document:", err)
	}

	log.Println("\n+++++ HTML content +++++")
	log.Println(html_whole_text(r))
}
