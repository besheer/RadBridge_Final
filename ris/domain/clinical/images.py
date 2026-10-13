"""Acquisition checks for exam completion, separate from nursing readiness."""
from domain.readiness import evaluate_required_series
from dataclasses import dataclass
from domain.clinical.workflow import TransitionDecision


@dataclass(frozen=True)
class ImageCompletionDecision(TransitionDecision):
    details: dict


def completion_image_policy(*, matched, pacs_present, error, image_count,
                            policy_defined, min_images=0, required_series='', series=()):
    count = max(0, int(image_count or 0))
    minimum = max(1, int(min_images or 0))
    # Empty series are not evidence that a required acquisition was sent.
    received = [row for row in series or () if int(row.get('instance_count') or 0) > 0]
    _, missing = evaluate_required_series(required_series, received)
    blockers = []
    if not matched:
        blockers.append('PACS identity match is not verified')
    if error or not pacs_present:
        blockers.append('PACS images could not be verified; retry the image check')
    if count < minimum:
        blockers.append(f'Images received: {count}; minimum required: {minimum}')
    if missing:
        blockers.append('Missing required series: ' + ', '.join(missing))
    warning = '' if policy_defined else 'Procedure image policy is incomplete; confirmed PACS images are required.'
    return {'allowed': not blockers, 'reason': '; '.join(blockers),
            'warning': warning, 'image_count': count, 'minimum': minimum,
            'identity_verified': bool(matched),
            'images_verified': bool(pacs_present and not error),
            'missing_series': missing, 'policy_defined': bool(policy_defined)}
