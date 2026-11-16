# Third-party references

This kit does not vendor EVerest, CitrineOS, or Stripe libraries.

CitrineOS Core and EVerest are referenced as upstream projects. Review their licenses
before redistribution. The source snapshot selected for CitrineOS declares Apache-2.0.
The compose overlay is an integration configuration intended to be merged with the
upstream Apache-2.0 compose files; upstream files are downloaded by the user and kept
under the gitignored vendor directory. Preserve upstream license/notice files there.

The seed/sequence initialization in scripts/stack.sh is adapted from
CitrineOS apps/mock-msp/scripts/ci/seed-citrine.sh at commit
4fd7599b91c2fb6e6065e7c9b94be69880cced27.
Those portions are Copyright 2026 Contributors to the CitrineOS Project,
licensed under Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0

The Python billing code, fixtures, tests, and project scripts are newly generated
research scaffolding. The team should select a project license before making its own
repository public. Do not assume that a library's license grants rights to any service
account, real customer data, private certificate, or payment credential.
