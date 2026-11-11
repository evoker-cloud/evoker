// SPDX-License-Identifier: AGPL-3.0-only
package agent

import (
	"context"
	"github.com/Autumn-27/norma/agentcore"
	"github.com/Autumn-27/norma/harness"
	"github.com/Autumn-27/norma/llm"
	actool "github.com/Autumn-27/norma/tool"
	"github.com/Autumn-27/norma/transcript"
	"io"
	"iter"
	"net/http"
	"strings"
	"testing"
)

// Exercise the actual SDK registry after NewSession, where automatic tools used
// to escape the earlier ARTEX filter. No provider, process or network is used.
func TestEvokerSessionDoesNotInjectSDKTools(t *testing.T) {
	t.Setenv("EVOKER_HOSTED", "true")
	for _, empty := range []bool{false, true} {
		called := false
		opts := agentcore.Options{EnableWebFetch: true, EnableWebSearch: true,
			Deps: harness.QueryDeps{CallModel: func(_ context.Context, req llm.CompletionRequest) iter.Seq2[llm.StreamEvent, error] {
				called = true
				for _, tool := range req.Tools {
					if tool.Name != "record_fact" {
						t.Errorf("unexpected SDK tool: %s", tool.Name)
					}
				}
				if empty && len(req.Tools) != 0 {
					t.Error("empty registry became default tools")
				}
				return func(yield func(llm.StreamEvent, error) bool) {
					yield(llm.StreamEvent{Type: llm.SEMessageDelta, StopReason: "end_turn"}, nil)
				}
			}}}
		if !empty {
			opts.Tools = []actool.CoreTool{actool.Build(actool.Spec{Name: "record_fact", Schema: map[string]any{"type": "object"}})}
		}
		s := agentcore.NewSession(evokerSessionOptions(opts))
		for _, err := range s.Prompt(context.Background(), "check registry") {
			if err != nil {
				t.Fatal(err)
			}
		}
		s.Close()
		if !called {
			t.Fatal("model registry was not observed")
		}
	}
}

func TestEvokerHostedBoundary(t *testing.T) {
	t.Setenv("EVOKER_HOSTED", "true")
	t.Setenv("EVOKER_MODEL_BASE_URL", "https://api.evoker.cloud/v1")
	t.Setenv("EVOKER_RUN_CREDENTIAL", "evrun_fixture")
	if (Config{ContextWindowK: 200}).CompactionWindow() != 8192 {
		t.Fatal("must preserve deployed context ceiling")
	}
	cfg := EvokerConfig(Config{BaseURL: "https://other.invalid", Proxy: "http://proxy.invalid", Model: "other"})
	if cfg.Proxy != "" || cfg.Model != "glm-5.3-flash-abliterated" || cfg.MaxTokens != 1024 || cfg.BaseURL != "https://api.evoker.cloud/v1" {
		t.Fatal("uncontrolled model configuration")
	}
	base := &fakeRT{}
	ctx := transcript.WithSessionID(context.Background(), "exp1-planner")
	req, _ := http.NewRequestWithContext(ctx, "POST", "https://api.evoker.cloud/v1/chat/completions", strings.NewReader("{}"))
	resp, err := evokerRoundTrip(base, req)
	if err != nil {
		t.Fatal(err)
	}
	io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	if base.seen.Header.Get("X-Evoker-Agent-Role") != "planner" || base.seen.Header.Get("Idempotency-Key") == "" {
		t.Fatal("missing attribution")
	}
	req.URL.Host = "attacker.invalid"
	if _, err := evokerRoundTrip(base, req); err == nil {
		t.Fatal("allowed another endpoint")
	}
	req.URL.Host = "api.evoker.cloud"
	req = req.WithContext(context.Background())
	if _, err := evokerRoundTrip(base, req); err == nil {
		t.Fatal("allowed unattributed request")
	}
	tools, _, cleanup := AugmentTools(ctx, "worker", append(actool.DefaultTools(), actool.Build(actool.Spec{Name: "record_fact"})))
	defer cleanup()
	if len(tools) != 2 || tools[0].Name() != "record_fact" || tools[1].Name() != "inspect_target" {
		t.Fatal("shell/file tools escaped hosted filter")
	}
}
