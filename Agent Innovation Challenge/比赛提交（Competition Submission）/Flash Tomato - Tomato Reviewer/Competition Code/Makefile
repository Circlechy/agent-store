# Downloads Makefile from openJiuwen/agent-core

ifeq ($(filter cmd.exe sh.exe,$(SHELL)),$(SHELL))
	CURL ?= curl.exe
else
	CURL ?= curl
endif

download:
	@$(CURL) -fsSL https://raw.gitcode.com/openJiuwen/agent-core/raw/develop/Makefile -o Makefile

.PHONY: download
.DEFAULT_GOAL := download
