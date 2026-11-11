// SPDX-License-Identifier: AGPL-3.0-only
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/Autumn-27/artex/server"
)

func main() {
	// A supervisor enforces CPU/RAM/storage/network limits and kills the entire
	// sandbox at the deadline. This entrypoint never opens an HTTP listener.
	if len(os.Args) != 3 {
		log.Fatal("Usage: evoker-artex <plan.json> <isolated-data-directory>")
	}
	f, err := os.Open(os.Args[1])
	if err != nil {
		log.Fatal("Cannot open plan")
	}
	var plan server.HostedPlan
	decoder := json.NewDecoder(io.LimitReader(f, 450001))
	decoder.DisallowUnknownFields()
	err = decoder.Decode(&plan)
	f.Close()
	if err != nil {
		log.Fatal("Invalid plan")
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	activate := make(chan struct{})
	go func() {
		scanner := bufio.NewScanner(os.Stdin)
		scanner.Buffer(make([]byte, 128), 128)
		if scanner.Scan() && scanner.Text() == "activate" {
			close(activate)
		} else {
			stop()
		}
	}()
	encoder := json.NewEncoder(os.Stdout)
	if err = server.RunHosted(ctx, os.Args[2], plan, activate, func(e server.HostedEvent) error { return encoder.Encode(e) }); err != nil {
		log.Print("Hosted assessment stopped")
		os.Exit(1)
	}
}
