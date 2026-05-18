// orchestrator.go —— 多 agent 编排：顺序 / 并行。整文件 cp 进项目即可。
package main

import (
	"context"
	"strings"
	"sync"
)

type Step struct {
	ID        string
	Agent     string
	Task      string
	DependsOn []string
}

const maxCtxChars = 400

func buildContext(results map[string]string, deps []string) string {
	parts := []string{}
	for _, d := range deps {
		v, ok := results[d]
		if !ok {
			continue
		}
		if len(v) > maxCtxChars {
			v = v[:maxCtxChars] + "...(已截断)"
		}
		parts = append(parts, "["+d+"]\n"+v)
	}
	return strings.Join(parts, "\n\n")
}

// RunSequential 按顺序跑；每步可以拿到 DependsOn step 的输出作 context。
func RunSequential(ctx context.Context, agents map[string]*Agent, workflow []Step) (map[string]string, error) {
	results := map[string]string{}
	for _, s := range workflow {
		out, err := agents[s.Agent].Execute(ctx, s.Task, buildContext(results, s.DependsOn))
		if err != nil {
			return results, err
		}
		results[s.ID] = out
	}
	return results, nil
}

// RunParallel 并发跑（彼此独立，不解 DAG）。
func RunParallel(ctx context.Context, agents map[string]*Agent, steps []Step) map[string]string {
	results := map[string]string{}
	var mu sync.Mutex
	var wg sync.WaitGroup
	for _, s := range steps {
		s := s
		wg.Add(1)
		go func() {
			defer wg.Done()
			out, err := agents[s.Agent].Execute(ctx, s.Task, "")
			if err != nil {
				out = "ERROR: " + err.Error()
			}
			mu.Lock()
			results[s.ID] = out
			mu.Unlock()
		}()
	}
	wg.Wait()
	return results
}
