package gohumble

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"github.com/gorilla/feeds"
	log "github.com/sirupsen/logrus"
)

const baseURL = "https://humblebundle.com"

type BundleItem struct {
	Category        string   `json:"category"`
	Title           string   `json:"title"`
	URL             string   `json:"url"`
	Description     string   `json:"description"`
	LongDescription string   `json:"long_description"`
	StartAt         string   `json:"start_at"`
	EndAt           string   `json:"end_at"`
	DaysLeft        *float64 `json:"days_left"`
	HoursLeft       *float64 `json:"hours_left"`
	MachineName     string   `json:"machine_name"`
	BundlesSold     float64  `json:"bundles_sold"`
	TileStamp       string   `json:"tile_stamp"`
}

type AllBundlesOutput struct {
	GeneratedAt string       `json:"generated_at"`
	Items       []BundleItem `json:"items"`
}

type UrgentBundlesOutput struct {
	GeneratedAt      string       `json:"generated_at"`
	ExpiresToday     []BundleItem `json:"expires_today"`
	ExpiresTomorrow  []BundleItem `json:"expires_tomorrow"`
	ExpiresWithin72h []BundleItem `json:"expires_within_72h"`
}

func Run() error {
	client := &http.Client{Timeout: 30 * time.Second}
	allItems := make([]BundleItem, 0)
	for _, category := range []string{"books", "games", "software"} {
		items, err := fetchCategory(client, category)
		if err != nil {
			return fmt.Errorf("fetching %s bundles: %w", category, err)
		}
		allItems = append(allItems, items...)
	}
	preserveStartDates(allItems)

	sort.Slice(allItems, func(i, j int) bool {
		return allItems[i].StartAt > allItems[j].StartAt
	})
	byCategory := make(map[string][]BundleItem)
	for _, item := range allItems {
		byCategory[item.Category] = append(byCategory[item.Category], item)
	}

	for _, category := range []string{"books", "games", "software"} {
		if err := writeFeedToFile(createFeedFromItems(byCategory[category], category), category); err != nil {
			return fmt.Errorf("writing %s.rss: %w", category, err)
		}
	}
	if err := writeFeedToFile(createFeedFromItems(allItems, "all"), "all"); err != nil {
		return fmt.Errorf("writing all.rss: %w", err)
	}
	if err := writeUrgentJSON(allItems); err != nil {
		return fmt.Errorf("writing urgent.json: %w", err)
	}
	if err := writeAllJSON(allItems); err != nil {
		return fmt.Errorf("writing all.json: %w", err)
	}
	return nil
}

func preserveStartDates(items []BundleItem) {
	data, err := os.ReadFile("all.json")
	if err != nil {
		return
	}
	var previous AllBundlesOutput
	if json.Unmarshal(data, &previous) != nil {
		return
	}
	byURL := make(map[string]string, len(previous.Items))
	for _, item := range previous.Items {
		byURL[item.URL] = item.StartAt
	}
	for i := range items {
		if start := byURL[items[i].URL]; start != "" {
			items[i].StartAt = start
		}
	}
}

func createFeed(products []Product, category string) feeds.Feed {
	items := make([]BundleItem, 0, len(products))
	for _, product := range products {
		item, ok := normalizeProduct(product, category)
		if ok {
			items = append(items, item)
		}
	}
	return createFeedFromItems(items, category)
}

func createFeedFromItems(items []BundleItem, category string) feeds.Feed {
	feed := feeds.Feed{
		Title:       fmt.Sprintf("Go Humble! RSS %s", strings.ToUpper(category[:1])+category[1:]),
		Link:        &feeds.Link{Href: "https://feuerlord2.github.io/Humble-RSS-Site/"},
		Description: fmt.Sprintf("Awesome RSS Feeds about HumbleBundle %s bundles!", category),
		Author:      &feeds.Author{Name: "Daniel Winter", Email: "DanielWinterEmsdetten+rss@gmail.com"},
		Created:     time.Now(),
	}

	validProducts := make([]*feeds.Item, 0, len(items))

	for _, item := range items {
		if item.StartAt == "" {
			log.WithField("product", item.Title).Warn("skipping product with empty StartAt")
			continue
		}

		dt, err := parseHumbleTime(item.StartAt)
		if err != nil {
			log.WithFields(log.Fields{
				"product": item.Title,
				"date":    item.StartAt,
			}).Warn("skipping product with invalid date format")
			continue
		}

		content := item.LongDescription
		if item.EndAt != "" {
			content = fmt.Sprintf(
				"%s<br/><br/><strong>Bundle ends:</strong> %s UTC",
				content,
				item.EndAt,
			)
		}
		if item.HoursLeft != nil {
			content = fmt.Sprintf(
				"%s<br/><strong>Time left:</strong> %.1f hours / %.2f days",
				content,
				*item.HoursLeft,
				*item.DaysLeft,
			)
		}

		validProducts = append(validProducts, &feeds.Item{
			Title:       item.Title,
			Link:        &feeds.Link{Href: item.URL},
			Content:     content,
			Created:     dt,
			Description: item.Description,
		})
	}

	feed.Items = validProducts
	sort.Slice(feed.Items, func(i, j int) bool { return feed.Items[i].Created.After(feed.Items[j].Created) })

	return feed
}

func normalizeProduct(product Product, category string) (BundleItem, bool) {
	if product.StartDateDatetime == "" {
		log.WithField("product", product.TileShortName).Warn("skipping product with empty StartDateDatetime")
		return BundleItem{}, false
	}

	url := product.ProductURL
	if url != "" && !strings.HasPrefix(url, "http") {
		url = fmt.Sprintf("%s%s", baseURL, url)
	}

	item := BundleItem{
		Category:        category,
		Title:           product.TileShortName,
		URL:             url,
		Description:     product.ShortMarketingBlurb,
		LongDescription: product.DetailedMarketingBlurb,
		StartAt:         product.StartDateDatetime,
		EndAt:           product.EndDateDatetime,
		MachineName:     product.MachineName,
		BundlesSold:     product.BundlesSoldDecimal,
		TileStamp:       product.TileStamp,
	}

	if item.Title == "" {
		item.Title = product.TileName
	}

	if product.EndDateDatetime != "" {
		endAt, err := parseHumbleTime(product.EndDateDatetime)
		if err == nil {
			delta := time.Until(endAt)
			hours := round(delta.Hours(), 1)
			days := round(delta.Hours()/24, 2)
			if hours < 0 {
				hours = 0
			}
			if days < 0 {
				days = 0
			}
			item.HoursLeft = &hours
			item.DaysLeft = &days
		}
	}

	return item, true
}

func parseHumbleTime(value string) (time.Time, error) {
	return time.Parse(time.RFC3339, value+"Z")
}

func round(value float64, places int) float64 {
	factor := 1.0
	for i := 0; i < places; i++ {
		factor *= 10
	}
	return float64(int(value*factor+0.5)) / factor
}

func parseProducts(data []byte, category string) ([]Product, error) {
	switch category {
	case "books":
		var books BooksData
		err := json.Unmarshal(data, &books)
		if err != nil {
			return nil, err
		}
		if len(books.Data.Books.Mosaic) == 0 {
			return nil, fmt.Errorf("no mosaic data found for %s", category)
		}
		return books.Data.Books.Mosaic[0].Products, nil
	case "games":
		var games GamesData
		err := json.Unmarshal(data, &games)
		if err != nil {
			return nil, err
		}
		if len(games.Data.Games.Mosaic) == 0 {
			return nil, fmt.Errorf("no mosaic data found for %s", category)
		}
		return games.Data.Games.Mosaic[0].Products, nil
	case "software":
		var software SoftwareData
		err := json.Unmarshal(data, &software)
		if err != nil {
			return nil, err
		}
		if len(software.Data.Software.Mosaic) == 0 {
			return nil, fmt.Errorf("no mosaic data found for %s", category)
		}
		return software.Data.Software.Mosaic[0].Products, nil
	default:
		return nil, fmt.Errorf("unknown category %s", category)
	}
}

func fetchCategory(client *http.Client, category string) ([]BundleItem, error) {
	resp, err := client.Get(fmt.Sprintf("https://www.humblebundle.com/%s", category))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected HTTP status %d", resp.StatusCode)
	}
	return parseCategoryHTML(resp.Body, category, time.Now().UTC())
}

func parseCategoryHTML(reader io.Reader, category string, observedAt time.Time) ([]BundleItem, error) {
	doc, err := goquery.NewDocumentFromReader(reader)
	if err != nil {
		return nil, err
	}
	if old := doc.Find("script#landingPage-json-data").First(); old.Length() > 0 {
		products, err := parseProducts([]byte(old.Text()), category)
		if err != nil {
			return nil, err
		}
		items := make([]BundleItem, 0, len(products))
		for _, product := range products {
			item, ok := normalizeProduct(product, category)
			if ok {
				items = append(items, item)
			}
		}
		if len(items) == 0 {
			return nil, fmt.Errorf("no valid bundles in %s listing", category)
		}
		return items, nil
	}

	var feedItems []struct {
		RelationTo string `json:"relationTo"`
		Value      struct {
			ProductKey         string   `json:"productKey"`
			URL                string   `json:"url"`
			Title              string   `json:"title"`
			EndDate            string   `json:"endDate"`
			Category           string   `json:"category"`
			ProductType        string   `json:"productType"`
			Description        string   `json:"description"`
			IncludedItemTitles []string `json:"includedItemTitles"`
			NumSold            *float64 `json:"numSold"`
		} `json:"value"`
	}
	found := false
	doc.Find("script").EachWithBreak(func(_ int, script *goquery.Selection) bool {
		content := strings.TrimSpace(script.Text())
		const prefix = "self.__next_f.push("
		if !strings.HasPrefix(content, prefix) || !strings.HasSuffix(content, ")") {
			return true
		}
		var chunk []json.RawMessage
		if json.Unmarshal([]byte(content[len(prefix):len(content)-1]), &chunk) != nil || len(chunk) < 2 {
			return true
		}
		var payload string
		if json.Unmarshal(chunk[1], &payload) != nil {
			return true
		}
		marker := `"feedItems":`
		index := strings.Index(payload, marker)
		if index < 0 {
			return true
		}
		found = true
		decoder := json.NewDecoder(strings.NewReader(payload[index+len(marker):]))
		if decoder.Decode(&feedItems) != nil {
			feedItems = nil
		}
		return false
	})
	if !found || len(feedItems) == 0 {
		return nil, fmt.Errorf("no bundle feedItems found in %s listing", category)
	}
	items := make([]BundleItem, 0, len(feedItems))
	for _, entry := range feedItems {
		value := entry.Value
		if entry.RelationTo != "algolia-hit" || value.ProductType != "humble-bundle" || value.Category != category || value.URL == "" || value.Title == "" {
			continue
		}
		endAt, err := time.Parse(time.RFC3339, value.EndDate)
		if err != nil || !endAt.After(observedAt) {
			continue
		}
		url := value.URL
		if strings.HasPrefix(url, "/") {
			url = baseURL + url
		}
		hours := round(endAt.Sub(observedAt).Hours(), 1)
		days := round(endAt.Sub(observedAt).Hours()/24, 2)
		description := value.Description
		if description == "$undefined" || description == "" {
			description = strings.Join(value.IncludedItemTitles, ", ")
		}
		item := BundleItem{
			Category: category, Title: value.Title, URL: url,
			Description:     description,
			LongDescription: strings.Join(value.IncludedItemTitles, ", "),
			StartAt:         observedAt.Format("2006-01-02T15:04:05"),
			EndAt:           endAt.UTC().Format("2006-01-02T15:04:05"),
			DaysLeft:        &days, HoursLeft: &hours,
			MachineName: value.ProductKey, TileStamp: category,
		}
		if value.NumSold != nil {
			item.BundlesSold = *value.NumSold
		}
		items = append(items, item)
	}
	if len(items) == 0 {
		return nil, fmt.Errorf("no valid bundles in %s feedItems", category)
	}
	return items, nil
}

func writeFeedToFile(feed feeds.Feed, category string) error {
	f, err := os.OpenFile(
		fmt.Sprintf("%s.rss", category),
		os.O_CREATE|os.O_TRUNC|os.O_WRONLY,
		0644,
	)
	if err != nil {
		return err
	}
	defer f.Close()

	w := bufio.NewWriter(f)
	rss, err := feed.ToRss()
	if err != nil {
		return err
	}

	if _, err := w.WriteString(rss); err != nil {
		return err
	}

	if err := w.Flush(); err != nil {
		return err
	}
	return nil
}

func writeAllJSON(items []BundleItem) error {
	output := AllBundlesOutput{
		GeneratedAt: time.Now().UTC().Format(time.RFC3339),
		Items:       items,
	}
	return writeJSONFile("all.json", output)
}

func writeUrgentJSON(items []BundleItem) error {
	now := time.Now().UTC()
	urgent := UrgentBundlesOutput{
		GeneratedAt: now.Format(time.RFC3339),
	}

	for _, item := range items {
		if item.EndAt == "" {
			continue
		}
		endAt, err := parseHumbleTime(item.EndAt)
		if err != nil {
			continue
		}
		hoursLeft := endAt.Sub(now).Hours()
		if hoursLeft < 0 {
			continue
		}
		if hoursLeft <= 24 {
			urgent.ExpiresToday = append(urgent.ExpiresToday, item)
		}
		if hoursLeft > 24 && hoursLeft <= 48 {
			urgent.ExpiresTomorrow = append(urgent.ExpiresTomorrow, item)
		}
		if hoursLeft <= 72 {
			urgent.ExpiresWithin72h = append(urgent.ExpiresWithin72h, item)
		}
	}

	return writeJSONFile("urgent.json", urgent)
}

func writeJSONFile(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0644)
}
