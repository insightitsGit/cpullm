# Submitting the CPU-LLM preprint

Files:

- `cpu-llm.tex` and `references.bib`: the source;
- `cpu-llm.pdf`: the compiled paper (9 pages).

Rebuild with `latexmk -pdf cpu-llm.tex`.

## Before you submit

1. Read the whole paper. You are the author and are responsible for every claim.
2. Edit the author block: affiliation (currently "Independent researcher") and, if you want, a contact email.
3. Keep or edit the "Acknowledgements and AI assistance" section. arXiv and most venues require AI use to be
   disclosed, and an AI cannot be listed as an author.
4. Check that the repository URL is public and that the 1.16.0 tag or release exists, so readers can reproduce it.

## Zenodo (DOI immediately, no endorsement)

1. Sign in at zenodo.org (a GitHub or ORCID login works).
2. Choose New upload. Upload `cpu-llm.pdf`, and optionally the source bundle (see below).
3. Set the upload type to Publication, subtype Preprint. Fill in the title, author, abstract (copy it from the
   .tex) and keywords: retrieval, evidence, neuro-symbolic, literature-based discovery, CPU.
4. Choose a licence. CC BY 4.0 is usual.
5. Under Related identifiers, add `https://github.com/insightitsGit/cpullm` as "is supplemented by".
6. Publish. The DOI is permanent; later fixes become new versions under the same concept DOI.

Optional: connect the GitHub repository to Zenodo (Zenodo, GitHub settings) so each GitHub release also gets
a software DOI. Cite that software DOI in a later version of the paper.

## arXiv

1. Create an account at arxiv.org. First-time submitters to cs.* usually need an **endorsement** from an
   existing author in that category. arXiv tells you when you start a submission, and you can request one there.
2. Category: primary `cs.IR` (information retrieval). Cross-list `cs.AI` and `cs.CL`.
3. Upload the source bundle, not only the PDF. arXiv compiles it. Build the bundle:

   ```shell
   latexmk -pdf cpu-llm.tex
   tar czf arxiv-source.tar.gz cpu-llm.tex cpu-llm.bbl references.bib
   ```

   Including the `.bbl` file avoids bibliography problems on arXiv.
4. Licence: choose CC BY 4.0 or the arXiv non-exclusive licence.
5. Comments field, for example: "9 pages. Software: https://github.com/insightitsGit/cpullm (version 1.16.0)".
6. arXiv moderators check that a paper is a substantive research contribution. A clear limitations section and
   real evaluation numbers help.

## Status

- Zenodo: published, DOI [10.5281/zenodo.24453546](https://doi.org/10.5281/zenodo.24453546).
- arXiv: not yet submitted. Once you have an endorsement, use this comments line:
  "9 pages. Also available at doi:10.5281/zenodo.24453546. Software: https://github.com/insightitsGit/cpullm
  (version 1.16.0)".
- A corrected paper goes to Zenodo as a new version of the same record, not as a new upload.
