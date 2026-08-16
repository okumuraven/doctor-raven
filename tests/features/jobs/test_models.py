from doctor_raven.features.jobs.models import JobListing, JobMatch


def test_job_listing_is_frozen():
    listing = JobListing(
        title="Engineer", company="Acme", url="https://x", location="Remote", source="Remotive", description="d"
    )
    try:
        listing.title = "Other"
        assert False, "expected FrozenInstanceError"
    except AttributeError:
        pass


def test_job_match_wraps_listing_and_reason():
    listing = JobListing(
        title="Engineer", company="Acme", url="https://x", location="Remote", source="Remotive", description="d"
    )
    match = JobMatch(listing=listing, reason="great fit")
    assert match.listing is listing
    assert match.reason == "great fit"
