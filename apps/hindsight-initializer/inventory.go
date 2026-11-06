package main

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"
)

type inventoryBuilder struct {
	root       string
	inv        Inventory
	seenHash   map[string]int
	seenID     map[string]bool
	totalBytes int64
	reserved   int
}

func newInventoryBuilder(root string, initial Inventory) *inventoryBuilder {
	b := &inventoryBuilder{root: root, inv: Inventory{Sources: append([]Source{}, initial.Sources...)},
		seenHash: map[string]int{}, seenID: map[string]bool{}}
	for i, s := range b.inv.Sources {
		b.seenID[s.ID] = true
		if s.Status == "ready" {
			b.inv.Ready++
			b.inv.Chars += s.Chars
			b.seenHash[s.Project+"\x00"+s.SHA] = i
			size := s.Bytes
			if size == 0 {
				if info, err := os.Stat(filepath.Join(root, "raw", s.ID+".md")); err == nil {
					size = info.Size()
				}
			}
			b.totalBytes += size
		} else if s.Status != "discovered" {
			b.inv.Skipped++
		}
	}
	return b
}

func (b *inventoryBuilder) add(s Source) error {
	s.ID = hashText(s.Agent + "\x00" + s.Path + "\x00" + s.SessionID)
	if b.seenID[s.ID] {
		return nil
	}
	if len(b.inv.Sources)+b.reserved >= discoveryLimit {
		return errors.New("超过 20,000 篇扫描上限，请缩小范围")
	}
	if s.Status == "" {
		if s.Agent != "document" {
			s.Text = strings.TrimSpace(redact(s.Text))
		}
		if s.Text == "" {
			s.Status, s.Reason = "skipped", "无正文"
		}
	}
	if utf8.ValidString(s.Text) {
		s.Chars = utf8.RuneCountInString(s.Text)
	}
	if s.Title == "" {
		s.Title = strings.TrimSuffix(filepath.Base(s.Path), filepath.Ext(s.Path))
	}
	s.Title = redact(s.Title)
	if s.Project == "" {
		s.Project = filepath.Dir(s.Path)
	}
	if s.Status == "" {
		s.SHA = hashText(s.Text)
		hashKey := s.Project + "\x00" + s.SHA
		if idx, ok := b.seenHash[hashKey]; ok {
			s.Status, s.Reason = "duplicate", b.inv.Sources[idx].ID
			b.inv.Sources[idx].Aliases = append(b.inv.Sources[idx].Aliases, s.ID)
		} else {
			s.Bytes = int64(len(s.Text))
			if b.totalBytes+s.Bytes > 256*1024*1024 {
				return errors.New("正文总量超过 256 MB，请分批扫描")
			}
			s.Status = "ready"
		}
		if err := atomicWrite(filepath.Join(b.root, "raw", s.ID+".md"), []byte(s.Text), 0600); err != nil {
			return err
		}
		if s.Status == "ready" {
			b.seenHash[hashKey] = len(b.inv.Sources)
			b.totalBytes += s.Bytes
			b.inv.Ready++
			b.inv.Chars += s.Chars
		}
	}
	if s.Status != "ready" {
		b.inv.Skipped++
	}
	// Source text lives in the private raw file, not in the in-memory catalog.
	s.Text = ""
	b.inv.Sources = append(b.inv.Sources, s)
	b.seenID[s.ID] = true
	return nil
}
