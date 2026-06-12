# Seeded prose corpus

Ten violations planted on purpose. The prose lints must catch 10/10
(DESIGN 9.2). Expected: 7 prose-banned, 1 prose-emdash, 1 F-05, 1 prose-long.

## A slop paragraph

We leverage the buffer pool to deliver a seamless experience. Let us delve
into the robust architecture and utilize every component. It's important to
note that the design is comprehensive.

## An em dash paragraph

The cache sits between the executor and the disk — every request passes
through it.

## A figure without a caption

![the architecture](figures/arch.png)

This paragraph is plain text where the takeaway caption should have been.

## A run-on sentence

The intake stage walks the source tree and routes each file to a parser and
then the secret filter strips anything that looks like a credential and then
the spans are written to the store and then the manifest records the hash
and then the trace timeline records what happened and then the merge stage
deduplicates the nodes and the edges before validation runs at the end of
everything.

## A clean paragraph for contrast

The model is one JSON document. Every fact in it carries a citation.
