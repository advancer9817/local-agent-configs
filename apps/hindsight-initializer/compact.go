package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"unicode/utf8"
)

type Evidence struct {
	ID      string `json:"id"`
	Title   string `json:"title"`
	Project string `json:"project"`
	Agent   string `json:"agent"`
	Date    string `json:"source_snapshot_time"`
	Text    string `json:"text"`
}

type Claim struct {
	Text    string   `json:"text"`
	Sources []string `json:"sources"`
}

type Proposal struct {
	Title  string  `json:"title"`
	Claims []Claim `json:"claims"`
}

type Acceptance struct {
	Safe        bool     `json:"safe"`
	Missing     []string `json:"missing"`
	Unsupported []string `json:"unsupported"`
	Scope       []string `json:"scope_issues"`
}

func (a Acceptance) accepted() bool {
	// Require explicit empty arrays, not absent fields or null.
	return a.Safe && a.Missing != nil && a.Unsupported != nil && a.Scope != nil &&
		len(a.Missing) == 0 && len(a.Unsupported) == 0 && len(a.Scope) == 0
}

type Product struct {
	ID         string            `json:"id"`
	Title      string            `json:"title"`
	Chars      int               `json:"chars"`
	Input      int               `json:"input_chars"`
	SourceIDs  []string          `json:"source_ids"`
	SHA        string            `json:"sha256"`
	Status     string            `json:"status"`
	Reason     string            `json:"reason,omitempty"`
	Content    string            `json:"-"`
	References map[string]Source `json:"source_map"`
}

func jsonText(v any) string { b, _ := json.Marshal(v); return string(b) }

func claimText(p Proposal, valid map[string]bool) (string, error) {
	if strings.TrimSpace(p.Title) == "" || len(p.Claims) == 0 {
		return "", errors.New("模型提案缺少标题或事实")
	}
	if utf8.RuneCountInString(p.Title) > 120 || strings.ContainsAny(p.Title, "\r\n") {
		return "", errors.New("模型标题过长或含换行，未作为文档身份接受")
	}
	covered := map[string]bool{}
	var b strings.Builder
	b.WriteString(strings.TrimSpace(p.Title) + "\n")
	for _, claim := range p.Claims {
		if strings.TrimSpace(claim.Text) == "" || len(claim.Sources) == 0 {
			return "", errors.New("事实或来源标注为空")
		}
		var labels []string
		for _, raw := range claim.Sources {
			for _, l := range strings.Split(raw, ",") {
				l = strings.TrimSpace(l)
				if !valid[l] {
					return "", errors.New("模型输出未知来源标签")
				}
				covered[l] = true
				labels = append(labels, l)
			}
		}
		b.WriteString(strings.TrimSpace(claim.Text) + " [" + strings.Join(labels, ",") + "]\n")
	}
	for l := range valid {
		if !covered[l] {
			return "", errors.New("模型提案遗漏整个来源 " + l)
		}
	}
	content := b.String()
	if redact(content) != content {
		return "", errors.New("模型输出含疑似凭据，拒绝接受")
	}
	return content, nil
}

func verifiedCompact(ctx context.Context, c Config, evidence []Evidence, dir string) (Proposal, string, error) {
	reportDetail(ctx, "检查已核验缓存", "")
	valid := map[string]bool{}
	for _, e := range evidence {
		valid[e.ID] = true
	}
	// Include the exact sanitized input and model settings in the cache identity.
	key := hashText(jsonText(evidence) + "\x00" + c.ModelURL + "\x00" + c.Model + "\x00compact-v1")
	cache := filepath.Join(dir, key)
	var approved struct {
		Proposal Proposal   `json:"proposal"`
		Check    Acceptance `json:"check"`
	}
	if readJSON(filepath.Join(cache, "approved.json"), &approved) == nil && approved.Check.accepted() {
		content, err := claimText(approved.Proposal, valid)
		return approved.Proposal, content, err
	}
	if err := atomicJSON(filepath.Join(cache, "evidence.json"), evidence); err != nil {
		return Proposal{}, "", err
	}
	var p Proposal
	if err := readJSON(filepath.Join(cache, "proposal.json"), &p); err != nil {
		reportDetail(ctx, "生成提炼稿", "")
		prompt := `把这些来源按主题归纳合并为精炼中文文档，目标约原文5%–10%（信息密集时可更长，不为比例牺牲关键事实）。不同项目/子主题以【主题】分段。每个来源至少被一条claim引用，sources只能用输入的id。日期指快照时间，不得编造成事件时间；仍需保留原文已明确的事件时间和历史限定。返回{title:string,claims:[{text:string,sources:[id,...]}]}。材料：` + jsonText(evidence)
		if err = modelJSON(ctx, c, prompt, &p); err != nil {
			return p, "", err
		}
		if err = atomicJSON(filepath.Join(cache, "proposal.json"), p); err != nil {
			return p, "", err
		}
	}
	content, err := claimText(p, valid)
	if err != nil {
		return p, "", err
	}
	for attempt := 0; attempt < 2; attempt++ {
		reportDetail(ctx, fmt.Sprintf("独立证据核验 · 第 %d 轮", attempt+1), "")
		var check Acceptance
		prompt := `独立核查：候选是否保留重要需求/决策/结论/未完成事项/关键标识/项目与时间边界，且没有新增无依据断言。用户授权大幅压缩，省略重复、过程、次要明细可以接受，不要把这些列入missing。尤其检查历史当现行、助手自述当已验证、不同项目状态混淆。无问题返回{safe:true,missing:[],unsupported:[],scope_issues:[]}；有问题safe:false，数组仅列严重问题，三个数组必须显式存在。来源：` + jsonText(evidence) + "\n候选：" + content
		if err = modelJSON(ctx, c, prompt, &check); err != nil {
			return p, "", err
		}
		if err = atomicJSON(filepath.Join(cache, fmt.Sprintf("check-%d.json", attempt)), check); err != nil {
			return p, "", err
		}
		if check.accepted() {
			approved.Proposal, approved.Check = p, check
			if err = atomicJSON(filepath.Join(cache, "approved.json"), approved); err != nil {
				return p, "", err
			}
			return p, content, nil
		}
		if attempt == 1 || len(check.Missing) == 0 || len(check.Unsupported) > 0 || len(check.Scope) > 0 {
			return p, "", errors.New("独立核验未通过，保留原文与检查记录")
		}
		var fix struct {
			Claims []Claim `json:"claims"`
		}
		if err = modelJSON(ctx, c, `仅根据来源补齐核验指出的重要遗漏，不改动原稿，不增加无依据内容，sources仅用来源id。返回{claims:[{text,sources}]}。遗漏：`+jsonText(check.Missing)+"\n来源："+jsonText(evidence), &fix); err != nil {
			return p, "", err
		}
		if len(fix.Claims) == 0 {
			return p, "", errors.New("遗漏未能补齐")
		}
		p.Claims = append(p.Claims, fix.Claims...)
		content, err = claimText(p, valid)
		if err != nil {
			return p, "", err
		}
	}
	return p, "", errors.New("核验失败")
}

func splitText(text string, limit int) []string {
	r := []rune(text)
	var out []string
	for len(r) > 0 {
		n := min(limit, len(r))
		if n < len(r) {
			for i := n; i > n/2; i-- {
				if r[i-1] == '\n' {
					n = i
					break
				}
			}
		}
		out = append(out, string(r[:n]))
		r = r[n:]
	}
	return out
}

func compactInventory(ctx context.Context, c Config, inv Inventory, root, sharedRoot string, log func(string)) ([]Product, error) {
	if err := c.validate(false, true); err != nil {
		return nil, err
	}
	cache := filepath.Join(sharedRoot, "candidates")
	completed, total := 0, 0
	for _, s := range inv.Sources {
		if s.Status == "ready" {
			total++
		}
	}
	reportProgress(ctx, "压缩与核验", completed, total, "", "篇来源")
	byProject := map[string][]Source{}
	for _, s := range inv.Sources {
		if s.Status == "ready" {
			reportDetail(ctx, "校验暂存正文", s.Path)
			b, err := os.ReadFile(filepath.Join(root, "raw", s.ID+".md"))
			if err != nil || hashText(string(b)) != s.SHA {
				return nil, errors.New("本地暂存正文指纹不匹配，请重新扫描")
			}
			s.Text = string(b)
			key := s.Project
			if key == "" {
				key = s.Agent
			}
			byProject[key] = append(byProject[key], s)
		}
	}
	keys := make([]string, 0, len(byProject))
	for k := range byProject {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	products := []Product{}
	for _, project := range keys {
		entries := byProject[project]
		sort.Slice(entries, func(i, j int) bool { return entries[i].ID < entries[j].ID })
		var batch []Source
		size := 0
		flush := func() error {
			if len(batch) == 0 {
				return nil
			}
			sources := append([]Source(nil), batch...)
			batch = nil
			size = 0
			ids := []string{}
			input := 0
			signature := ""
			for _, s := range sources {
				ids = append(ids, s.ID)
				input += s.Chars
				signature += s.ID + ":" + s.SHA + "\n"
				ids = append(ids, s.Aliases...)
			}
			pid := hashText(signature + c.ModelURL + c.Model)
			product := Product{ID: pid, SourceIDs: ids, Input: input, Status: "review_required"}
			product.References = map[string]Source{}
			for i, source := range sources {
				// Source.Text is excluded by its JSON tag: provenance contains no raw transcript.
				product.References[fmt.Sprintf("S%d", i+1)] = source
			}
			log(fmt.Sprintf("提炼 %d 个来源 · %d 字", len(sources), input))
			reportProgress(ctx, "压缩与核验", completed, total, project, "篇来源")
			var evidence []Evidence
			var prepErr error
			for i, s := range sources {
				evidence = append(evidence, Evidence{fmt.Sprintf("S%d", i+1), s.Title, s.Project, s.Agent, s.Modified, s.Text})
			}
			if prepErr == nil {
				proposal, body, err := verifiedCompact(ctx, c, evidence, cache)
				prepErr = err
				if err == nil {
					product.Title, product.Content = proposal.Title, body
					product.Content += "\n注：以上是来源历史记录，快照时间不证明当前状态或新的授权。\n"
					product.SHA = hashText(product.Content)
					product.Chars = utf8.RuneCountInString(product.Content)
					product.Status = "approved"
					if product.Chars >= input {
						product.Status, product.Reason = "no_gain", "核验稿不比原文短，暂不上传"
					}
					if err = atomicWrite(filepath.Join(root, "products", pid+".md"), []byte(product.Content), 0600); err != nil {
						return err
					}
				}
			}
			if prepErr != nil {
				product.Reason = prepErr.Error()
			}
			products = append(products, product)
			if err := atomicJSON(filepath.Join(root, "products.json"), products); err != nil {
				return err
			}
			completed += len(sources)
			reportProgress(ctx, "压缩与核验", completed, total, project, "篇来源")
			if ctx.Err() != nil {
				return ctx.Err()
			}
			log(fmt.Sprintf("%s · %d → %d 字", product.Status, input, product.Chars))
			return nil
		}
		for _, s := range entries {
			reportProgress(ctx, "压缩与核验", completed, total, s.Path, "篇来源")
			if s.Chars > 16000 {
				log(fmt.Sprintf("分段核验长文：%s · %d 字", s.Title, s.Chars))
				var summaries []string
				var prepareErr error
				parts := splitText(s.Text, 16000)
				for j, part := range parts {
					reportDetail(ctx, fmt.Sprintf("长文分段 %d/%d · %s", j+1, len(parts), s.Title), s.Path)
					label := fmt.Sprintf("P%d", j+1)
					_, body, err := verifiedCompact(ctx, c, []Evidence{{label, s.Title, s.Project, s.Agent, s.Modified, part}}, cache)
					if err != nil {
						prepareErr = err
						break
					}
					summaries = append(summaries, body)
				}
				if prepareErr == nil {
					s.Text = strings.Join(summaries, "\n")
					if utf8.RuneCountInString(s.Text) > 28000 {
						prepareErr = errors.New("分段摘要仍超过 28,000 字，未截断归档")
					}
				}
				if prepareErr != nil {
					products = append(products, Product{ID: hashText(s.ID + s.SHA + c.Model), Title: s.Title, Input: s.Chars, SourceIDs: append([]string{s.ID}, s.Aliases...), Status: "review_required", Reason: prepareErr.Error()})
					if err := atomicJSON(filepath.Join(root, "products.json"), products); err != nil {
						return products, err
					}
					if ctx.Err() != nil {
						return products, ctx.Err()
					}
					log("长文核验未通过，保留原文：" + s.Title)
					completed++
					reportProgress(ctx, "压缩与核验", completed, total, s.Path, "篇来源")
					continue
				}
			}
			effective := utf8.RuneCountInString(s.Text)
			if size+effective > 16000 || len(batch) >= 20 {
				if err := flush(); err != nil {
					return products, err
				}
			}
			batch = append(batch, s)
			size += effective
			if effective > 16000 {
				if err := flush(); err != nil {
					return products, err
				}
			}
		}
		if err := flush(); err != nil {
			return products, err
		}
	}
	return products, nil
}
