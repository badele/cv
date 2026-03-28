# CV

This CV website is generated automatically from a CV written in a LaTeX
document. Here are the steps:

- Convert the LaTeX document to PDF
- Convert the PDF to HTML (for the web version)
- Generate the personal landing page
- Publish the pages on GitHub Pages

## Automation

- GitHub stars are checked daily at 01:00 UTC by a scheduled workflow.
- If `latex/github.tex` changes, the update is committed to `main`, which
  triggers the `build-cv` workflow to regenerate the PDF/HTML outputs.

## Source:

Thanks to [Jan Küster](https://github.com/jankapunkt) for his
[latexcv](https://github.com/jankapunkt/latexcv) project.
