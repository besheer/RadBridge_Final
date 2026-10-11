"""Runtime-bound web.components.operations; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0491(_rb):
    def admin_qa():
        counts={
            'outbox_pending':_rb.EventOutbox.query.filter_by(status='PENDING').count(),
            'outbox_failed':_rb.EventOutbox.query.filter_by(status='FAILED').count(),
            'users':_rb.User.query.count(),
            'orders':_rb.Order.query.count(),
            'patients':_rb.Patient.query.count(),
        }
        recent=_rb.EventOutbox.query.order_by(_rb.EventOutbox.id.desc()).limit(100).all()
        return _rb.render_template('admin_qa.html',counts=counts,recent=recent)
    return admin_qa


def install_0834(_rb):
    @_rb.login_required
    def api_ops_health():
        snap=_rb.workflow_command_snapshot()
        return _rb.jsonify({'ok':True,'pacs_online':snap['pacs_online'],'problem_count':len(snap['problems']),
          'no_images':len(snap['no_images']),'unassigned':len(snap['unassigned']),
          'pacs_inbox_pending':_rb.PacsStudyInbox.query.filter(_rb.PacsStudyInbox.state.in_(['NEW','REVIEW','ERROR'])).count(),
          'transfer_pending':_rb.PacsTransferJob.query.filter(_rb.PacsTransferJob.status.in_(['PENDING','FAILED'])).count()})
    return api_ops_health

