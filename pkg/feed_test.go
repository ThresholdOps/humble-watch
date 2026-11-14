package gohumble

import (
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"
)

func nextPage(payload string) string {
	encoded, _ := json.Marshal([]any{1, payload})
	return fmt.Sprintf("<html><script>self.__next_f.push(%s)</script></html>", encoded)
}

func TestParseCategoryHTMLReadsCurrentListing(t *testing.T) {
	page := nextPage(`4f:["$","$L7e",null,{"feedItems":[{"relationTo":"algolia-hit","value":{"productKey":"python_books","url":"/books/python-books","title":"Python Books","endDate":"2026-11-30T19:00:00.000Z","category":"books","productType":"humble-bundle","includedItemTitles":["Python Basics","Advanced Python"]}}]}]`)
	items, err := parseCategoryHTML(strings.NewReader(page), "books", time.Date(2026, 11, 14, 18, 0, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 {
		t.Fatalf("expected one bundle, got %d", len(items))
	}
	item := items[0]
	if item.Title != "Python Books" || item.URL != "https://humblebundle.com/books/python-books" || item.EndAt != "2026-11-30T19:00:00" || item.StartAt != "2026-11-14T18:00:00" {
		t.Fatalf("unexpected bundle: %+v", item)
	}
	if !strings.Contains(item.LongDescription, "Advanced Python") {
		t.Fatalf("included titles missing from searchable description: %+v", item)
	}
}

func TestParseCategoryHTMLRejectsMissingListing(t *testing.T) {
	_, err := parseCategoryHTML(strings.NewReader("<html><body>new page with no bundle data</body></html>"), "books", time.Now())
	if err == nil {
		t.Fatal("missing listing must fail so generation cannot publish an empty snapshot")
	}
}
