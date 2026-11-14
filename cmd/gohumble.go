package main

import (
	"log"

	gohumble "github.com/Feuerlord2/Humble-RSS-Site/pkg"
)

func main() {
	if err := gohumble.Run(); err != nil {
		log.Fatal(err)
	}
}
