
# Copyright (C) 2014 Ivan D Vasin


# flags -----------------------------------------------------------------------

UPGRADE := 0
ifneq "$(U)" ""
	UPGRADE := $(U)
endif
RECURSIVE := 0
ifneq "$(R)" ""
	RECURSIVE := $(R)
endif


# core commands ---------------------------------------------------------------

PYENV := $(VIRTUAL_ENV)
SHELL := /usr/bin/env bash

ifneq "$(PYENV)" ""
	PYTHON := '$(PYENV)/bin/python'
else
	PYTHON := /usr/bin/env python
endif
PYTHON_SETUP := $(PYTHON) setup.py

ifneq "$(PYENV)" ""
	PIP := '$(PYENV)/bin/pip'
else
	PIP := /usr/bin/env pip
endif
PIP_INSTALL := $(PIP) install
ifneq "$(UPGRADE)" "0"
	PIP_INSTALL := $(PIP_INSTALL) --upgrade
endif


# project info ----------------------------------------------------------------

NAME := $(shell $(PYTHON_SETUP) --name)
DESCRIPTION := $(shell $(PYTHON_SETUP) --description)
VERSION_NOSUFFIX := $(shell $(PYTHON_SETUP) --version)
PARENT_NAMESPACE_PKG := \
    $(shell python -c "import setup; print setup.PARENT_NAMESPACE_PKG" \
            2> /dev/null)

# packaging options -----------------------------------------------------------

SIGNER_NAME := Ivan D Vasin <nisavid@gmail.com>

WHEEL_TOOL := \
    $(shell path="$$(which wheel 2> /dev/null)"; \
            if [[ -n "$$path" ]]; then \
                echo \'$$path\'; \
            fi)


# deployment options ----------------------------------------------------------

CHEESESHOP := deli


# doc files and commands ------------------------------------------------------

DOC_BUILDDIR := build/sphinx
DOC_SRCDIR := doc
DOC_INSTALL_PREFIX := /usr/local/share/doc

DOC_CONFIG := $(DOC_SRCDIR)/conf.py
DOC_CONFIG_TEMPLATE := $(DOC_SRCDIR)/conf.tmpl.py
DOC_EXCLUDE_MODULES := $(DOC_SRCDIR)/exclude-modules
DOC_INSTALL_DIR := $(DOC_INSTALL_PREFIX)/$(NAME)
DOC_MAKE_BAT := $(DOC_SRCDIR)/make.bat
DOC_MAKE_BAT_TEMPLATE := $(DOC_SRCDIR)/make.tmpl.bat
DOC_MAKEFILE := $(DOC_SRCDIR)/Makefile
DOC_MAKEFILE_TEMPLATE := $(DOC_SRCDIR)/Makefile.tmpl

DOC_GEN_REST := '$(PYENV)/bin/project-doc-gen-rest'
DOC_GEN_REST_ARGS := \
    $$([[ -f '$(DOC_EXCLUDE_MODULES)' ]] \
        && { echo -n '--excluded-modules '; \
             cat '$(DOC_EXCLUDE_MODULES)' | xargs; \
           })
DOC_GEN_REST_FILES := \
    $$([[ -d '$(DOC_SRCDIR)' ]] \
        && { find '$(DOC_SRCDIR)' -mindepth 1 -maxdepth 1 -name '*.rst'; \
             if [[ -n "$(PARENT_NAMESPACE_PKG)" ]]; then \
                 echo "$(DOC_SRCDIR)/$(PARENT_NAMESPACE_PKG)"; \
             fi; \
           } | xargs)


# version control system ------------------------------------------------------

VCS := $$(git status --porcelain > /dev/null 2>&1; \
          if [[ $$? -eq 0 ]]; then \
              echo 'git'; \
          else \
              git svn info > /dev/null 2>&1; \
              if [[ $$? -eq 0 ]]; then \
                  echo 'git-svn'; \
              else \
                  svn info > /dev/null 2>&1; \
                  if [[ $$? -eq 0 ]]; then \
                      echo 'svn'; \
                  fi; \
              fi; \
          fi)
ifneq "$(VCS)" ""
	VCS_HAS_UNCOMMITTED_CHANGES := \
        $$(uncommitted_changed_files=$$(case '$(VCS)' in \
                                            'svn') \
                                                svn --non-interactive status; \
                                                ;; \
                                            'git' | 'git-svn') \
                                                git status --porcelain; \
                                                ;; \
                                        esac \
                                         | wc --lines); \
           if [[ "$$uncommitted_changed_files" -ne 0 ]]; then \
               echo 1; \
           else \
               echo 0; \
           fi
	VCS_HAS_LOCAL_CHANGES := \
        $$(case '$(VCS)' in \
               'svn') \
                   echo $(VCS_HAS_UNCOMMITTED_CHANGES); \
                   ;; \
               'git' | 'git-svn') \
                   case '$(VCS)' in \
                       'git') \
                           central_version='origin/master'; \
                           ;; \
                       'git-svn') \
                           central_version='git-svn'; \
                           ;; \
                   esac; \
                   committed_local_changes=$$(git diff --name-status \
                                                       \"$$central_version\" \
                                               | wc --lines); \
                   if [[ "$(VCS_HAS_UNCOMMITTED_CHANGES)" -ne 0 \
                         || "$$committed_local_changes" -ne 0 ]]; then \
                       echo 1; \
                   else \
                       echo 0; \
                   fi; \
                   ;; \
           esac)
endif


# version string --------------------------------------------------------------

ifeq "$(VCS_HAS_LOCAL_CHANGES)" "0"
	last_commit_date_cmd := \
        case '$(VCS)' in \
            'git') \
                git log -1 --format=format:%ci \
                ;; \
            'git-svn' | 'svn') \
                case '$(VCS)' in \
                    'git-svn') \
                        git svn info; \
                        ;; \
                    'svn') \
                        svn info; \
                        ;; \
                esac \
                 | grep 'Last Changed Date' \
                 | sed 's/.*Date: \([^()]\+\).*/\1/'; \
                ;; \
        esac
	VERSION_RELEASE := $(shell date -u +%Y%m%d%H%M%S
                                    -d "$$($(last_commit_date_cmd))")
else
	ifneq "$(VCS_HAS_UNCOMMITTED_CHANGES)" "0"
		VERSION_RELEASE := dev$(shell date -u +%Y%m%d%H%M%S)
	else
		ifeq "$(VCS)" "git"
			VERSION_RELEASE := \
                dev$(shell date -u +%Y%m%d%H%M%S \
                                -d "$$(git log -1 --format=format:%ci)")
		endif
	endif
endif
USE_VERSION_SUFFIX := $(VCS_HAS_LOCAL_CHANGES)
ifneq "$(USE_VERSION_SUFFIX)" "0"
	VERSION_SUFFIX := .$(VERSION_RELEASE)
	VERSION := $(VERSION_NOSUFFIX)$(VERSION_SUFFIX)
	SETUP_OPT_TAG_BUILD := --tag-build '$(VERSION_SUFFIX)'
	SET_VERSION_SUFFIX := \
        $(PYTHON_SETUP) setopt --command egg_info --option tag-build \
                               --set-value '$(VERSION_SUFFIX)'
	UNSET_VERSION_SUFFIX := \
        $(PYTHON_SETUP) setopt --command egg_info --option tag-build --remove \
         && if [[ ! -s setup.cfg ]]; then \
                rm -f setup.cfg; \
            fi
else
	VERSION := $(VERSION_NOSUFFIX)
	SET_VERSION_SUFFIX := true
	UNSET_VERSION_SUFFIX := true
endif


# generated files -------------------------------------------------------------

BYTECODE_FILES := $$(find . -regex '.+\.py[co]')
EGG_INFO_DIR := $(shell echo $(NAME) | sed 's/-/_/g').egg-info
EDINSTALLED_EXT_MODULES := \
    $$(python setup.py build_ext -n \
        | grep "building '.*' extension" \
        | sed "s/.*'\([^']*\)'.*/\1/" \
        | while read ext; do \
              find . -maxdepth 1 -regex "\./$$ext\.\(so\|pyd\)"; \
          done)
SETUP_FILES_TO_CLEAN := \
    $(BYTECODE_FILES) build dist $(EGG_INFO_DIR) $(EDINSTALLED_EXT_MODULES)

DOC_FILES_TO_CLEAN := \
    '$(DOC_CONFIG)' '$(DOC_MAKE_BAT)' '$(DOC_MAKEFILE)' $(DOC_GEN_REST_FILES) \
    '$(DOC_BUILDDIR)'


# setup script commands -------------------------------------------------------

SETUP_CMD_BDIST_EGG := bdist_egg --plat-name generic
SETUP_CMD_BDIST_WHEEL := bdist_wheel
SETUP_CMD_BUILD := build
SETUP_CMD_BUILD_DOC := build_sphinx
SETUP_CMD_EDINSTALL := develop
SETUP_CMD_EGG_INFO := egg_info $(SETUP_OPT_TAG_BUILD)
SETUP_CMD_INSTALL := install
SETUP_CMD_REGISTER := \
    register --repository '$(CHEESESHOP)' --strict --show-response
SETUP_CMD_SDIST := sdist
SETUP_CMD_TEST := test
SETUP_CMD_UPLOAD_NOSIGN := upload --repository '$(CHEESESHOP)' --show-response

SETUP_CMD_UPLOAD := \
    $(SETUP_CMD_UPLOAD_NOSIGN) --sign --identity '$(SIGNER_NAME)'


# egg info --------------------------------------------------------------------

EGG_INFO_VERSION := \
    $(shell grep '^Version: ' $(EGG_INFO_DIR)/PKG-INFO 2> /dev/null \
             | sed 's/Version: //')

ifeq "$(EGG_INFO_VERSION)" "$(VERSION)"
	PYTHON_SETUP_EGG_INFO := true
	SETUP_CMD_EGG_INFO :=
else
	PYTHON_SETUP_EGG_INFO := $(PYTHON_SETUP) $(SETUP_CMD_EGG_INFO)
endif

EGG_INFO_EXTRAS := \
    $(shell $(PYTHON_SETUP_EGG_INFO) > /dev/null \
             && grep '^\[.*\]$$' $(EGG_INFO_DIR)/requires.txt 2> /dev/null \
                 | sed 's/\[\(.*\)\]/\1/' \
                 | xargs)


# dependents of egg info ------------------------------------------------------

ifeq "$(EGG_INFO_EXTRAS)" ""
	PIP_EDINSTALL := $(PIP_INSTALL) --editable .
else
	PIP_EDINSTALL := \
        $(PIP_INSTALL) --editable .[$(shell echo $(EGG_INFO_EXTRAS) \
                                             | sed 's/ /,/g')]
endif
ifneq "$(UPGRADE)" "0"
	PIP_EDINSTALL := $(PIP_EDINSTALL) --upgrade
endif


# targets ---------------------------------------------------------------------

all: build

build:
	$(PYTHON_SETUP) $(SETUP_CMD_BUILD)

check:
	$(PYTHON_SETUP) $(SETUP_CMD_EGG_INFO) $(SETUP_CMD_TEST)

clean: setup-clean doc-clean

doc-build:
	if [[ ! -f '$(DOC_CONFIG_TEMPLATE)' ]]; then \
        message='no Sphinx configuration template found at' \
        message+=" '$(DOC_CONFIG_TEMPLATE)'"; \
        echo $$message; \
        false; \
    fi
	
	cp '$(DOC_CONFIG_TEMPLATE)' '$(DOC_CONFIG)'
	cp '$(DOC_MAKE_BAT_TEMPLATE)' '$(DOC_MAKE_BAT)'
	cp '$(DOC_MAKEFILE_TEMPLATE)' '$(DOC_MAKEFILE)'
	
	project=$$(echo '$(NAME)' | sed 's_/_\\/_g') \
     && sed -i'' -e "s/^\(project =\).*$$/\1 u'$$project'/" '$(DOC_CONFIG)' \
     && sed -i'' -e "s/^\(set PROJECT=\).*$$/\1$$project/" '$(DOC_MAKE_BAT)' \
     && sed -i'' -e "s/^\(PROJECT =\).*$$/\1 $$project/" '$(DOC_MAKEFILE)'
	description=$$(echo '$(DESCRIPTION)' | sed 's_/_\\/_g') \
     && sed -i'' -e "s/^\(description =\).*$$/\1 u'$$description'/" \
            '$(DOC_CONFIG)'
	version=$$(echo '$(VERSION_NOSUFFIX)' | sed 's_/_\\/_g') \
     && sed -i'' -e "s/^\(version =\).*$$/\1 '$$version'/" '$(DOC_CONFIG)'
	release=$$(echo '$(VERSION)' | sed 's_/_\\/_g') \
     && sed -i'' -e "s/^\(release =\).*$$/\1 '$$release'/" '$(DOC_CONFIG)'
	
	$(DOC_GEN_REST) && $(PYTHON_SETUP) $(SETUP_CMD_BUILD_DOC)

doc-clean:
	rm -rf $(DOC_FILES_TO_CLEAN)

doc-install: doc-build
	mkdir -p '$(DOC_INSTALL_DIR)'
	find $(DOC_BUILDDIR) -mindepth 1 -maxdepth 1 \
     | while read file; do \
           cp -a "$$file" '$(DOC_INSTALL_DIR)/'; \
       done

doc-uninstall:
	if [[ -d '$(DOC_INSTALL_DIR)' ]]; then \
        rm -rf '$(DOC_INSTALL_DIR)/*'; \
    fi

edinstall:
	unset fail; \
    if [[ '$(RECURSIVE)' -ne 0 ]]; then \
        projects=$$(find-pyprojects --path .) \
         && dirs=$$(find-devel-pyprojects --include-deps \
                                          --update \
                                          --format '{location}' \
                                          --sort deps \
                                          $$projects) \
         && dep_dirs=$$(echo $$dirs | uniq | head -n -1) \
         && for dep_dir in $$dep_dirs; do \
                $(MAKE) RECURSIVE=0 -C $$dep_dir $@ \
                 || { fail=1; break; }; \
            done \
         || fail=1; \
    fi; \
    [[ ! "$$fail" ]]
	
	$(SET_VERSION_SUFFIX) \
     && { $(PIP_EDINSTALL); \
          ret=$$?; \
          $(UNSET_VERSION_SUFFIX); \
          ret_=$$?; if [[ "$$ret" -eq 0 ]]; then ret=$$ret_; fi; \
          exit $$ret; \
        }

egg:
	$(PYTHON_SETUP) $(SETUP_CMD_EGG_INFO) $(SETUP_CMD_BDIST_EGG)

egginfo:
	$(PYTHON_SETUP_EGG_INFO)

install:
	unset fail; \
    if [[ '$(RECURSIVE)' -ne 0 ]]; then \
        projects=$$(find-pyprojects --path .) \
         && dirs=$$(find-devel-pyprojects --include-deps \
                                          --update \
                                          --format '{location}' \
                                          --sort deps \
                                          $$projects) \
         && dep_dirs=$$(echo $$dirs | uniq | head -n -1) \
         && for dep_dir in $$dep_dirs; do \
                $(MAKE) RECURSIVE=0 -C $$dep_dir $@ \
                 || { fail=1; break; }; \
            done \
         || fail=1; \
    fi; \
    [[ ! "$$fail" ]]
	
	$(SET_VERSION_SUFFIX) \
     && { $(PIP_INSTALL) .; \
          ret=$$?; \
          $(UNSET_VERSION_SUFFIX); \
          ret_=$$?; if [[ "$$ret" -eq 0 ]]; then ret=$$ret_; fi; \
          exit $$ret; \
        }

sdist:
	$(PYTHON_SETUP) $(SETUP_CMD_EGG_INFO) $(SETUP_CMD_SDIST)

setup-clean:
	rm -rf $(SETUP_FILES_TO_CLEAN)

uninstall:
	$(PIP) uninstall $(NAME) < <(yes)

upload:
	WHEEL_TOOL=$(WHEEL_TOOL) \
        $(PYTHON_SETUP) \
            $(SETUP_CMD_EGG_INFO) \
            $(SETUP_CMD_SDIST) \
            $(SETUP_CMD_BDIST_WHEEL) \
            $(SETUP_CMD_BDIST_EGG) \
            $(SETUP_CMD_REGISTER) \
            $(SETUP_CMD_UPLOAD)

upload-nosign:
	$(PYTHON_SETUP) \
        $(SETUP_CMD_EGG_INFO) \
        $(SETUP_CMD_SDIST) \
        $(SETUP_CMD_BDIST_WHEEL) \
        $(SETUP_CMD_BDIST_EGG) \
        $(SETUP_CMD_REGISTER) \
        $(SETUP_CMD_UPLOAD_NOSIGN)

wheel:
	WHEEL_TOOL=$(WHEEL_TOOL) \
        $(PYTHON_SETUP) $(SETUP_CMD_EGG_INFO) $(SETUP_CMD_BDIST_WHEEL)
