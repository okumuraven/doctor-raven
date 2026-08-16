"""Data models for job listings and resume-matched results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JobListing:
    title: str
    company: str
    url: str
    location: str
    source: str
    description: str


@dataclass(frozen=True)
class JobMatch:
    listing: JobListing
    reason: str
