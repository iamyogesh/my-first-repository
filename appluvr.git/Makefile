# You can set these variables from the command line.
PYTHON   			= env/bin/python 
SETUP    			= setup.py
BUILDDIR 			= build
DISTDIR				= dist
DOCDIR				= appluvr/static/docs

.PHONY: help clean html dirhtml singlehtml pickle json htmlhelp qthelp devhelp epub latex latexpdf text man changes linkcheck doctest egg docs

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  docs       to make the HTML sphinx docs"
	@echo "  clean       to remove intermediate files"
	@echo "  egg        to make a binary egg file for distribution"
	@echo "  canarys    to push the build and docs to Canarys servers"

clean:
	-rm -rf $(BUILDDIR)/*
	-rm -rf appluvr_views.egg-info
	find . -name "*.pyc" -delete
	@echo
	@echo "Clean finished. Intermediate build files and binaries are deleted"

egg:
	$(PYTHON)  $(SETUP) bdist_egg
	@echo
	@echo "Build finished. The egg is in $(DISTDIR)."

canarys: egg
	@echo
	@echo "Copying files - please authenticate if needed"
	scp -r $(DISTDIR)/* canarys@182.71.252.172:.builds
	scp -r $(BUILDDIR)/sphinx/html/* canarys@182.71.252.172:~/.builds/docs
