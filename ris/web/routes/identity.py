"""Runtime-bound web.routes.identity; dependencies are supplied at composition.

Legacy behavior is preserved; new policies belong in the independent domain layer.
"""

def install_0147(_rb):
    @_rb.app.route('/login',methods=['GET','POST'])
    def login():
        if _rb.request.method=='POST':
            u=_rb.User.query.filter_by(username=_rb.request.form.get('username','').strip()).first()
            if u and u.active and _rb.check_password_hash(u.password_hash,_rb.request.form.get('password','')):
                _rb.session['uid']=u.id; _rb.audit('LOGIN','user',u.id,'Successful login'); _rb.db.session.commit()
                return _rb.redirect(_rb._safe_login_next(_rb.request.args.get('next')))
            attempted=(_rb.request.form.get('username','').strip()[:80] or 'UNKNOWN')
            _rb.db.session.add(_rb.AuditLog(
                user_id=(u.id if u else None),username=attempted,
                action='LOGIN_FAILED',entity='user',entity_id=str(u.id if u else ''),
                details='reason=INVALID_CREDENTIALS',
                ip=_rb._security_audit_ip()
            ))
            _rb.db.session.commit()
            _rb.flash('Invalid username or password.','danger')
        return _rb.render_template('login.html')
    return login


def install_0148(_rb):
    @_rb.app.route('/logout')
    def logout():
        _rb.session.clear(); return _rb.redirect(_rb.url_for('login'))
    return logout


def install_0156(_rb):
    @_rb.app.route('/profile/password',methods=['GET','POST'])
    @_rb.login_required
    def change_password():
        u=_rb.current_user()
        if _rb.request.method=='POST':
            if not _rb.check_password_hash(u.password_hash,_rb.request.form.get('current_password','')):
                _rb.flash('Current password is incorrect.','danger')
            elif len(_rb.request.form.get('new_password',''))<10:
                _rb.flash('New password must be at least 10 characters.','danger')
            elif _rb.request.form.get('new_password')!=_rb.request.form.get('confirm_password'):
                _rb.flash('Password confirmation does not match.','danger')
            else:
                u.password_hash=_rb.generate_password_hash(_rb.request.form['new_password']); _rb.audit('PASSWORD_CHANGE','user',u.id,'')
                _rb.db.session.commit(); _rb.flash('Password changed.','success'); return _rb.redirect(_rb.url_for('dashboard'))
        return _rb.render_template('change_password.html')
    return change_password


def install_0551(_rb):
    @_rb.app.post('/admin/users/<int:user_id>/reset-password')
    @_rb.require_perm('users.manage')
    def admin_user_reset_password(user_id):
        u=_rb.User.query.get_or_404(user_id)
        from user_access_policy import require_manage_target
        require_manage_target(user=u)
        password=_rb.request.form.get('new_password','')
        if len(password)<10:
            _rb.flash('Temporary password must be at least 10 characters.','danger'); return _rb.redirect(_rb.url_for('admin_users'))
        u.password_hash=_rb.generate_password_hash(password)
        u.must_change_password=True
        u.password_changed_at=_rb.datetime.utcnow()
        _rb.audit('PASSWORD_RESET','user',u.id,'Temporary password issued; change required')
        _rb.db.session.commit(); _rb.flash('Password reset. User must change it at next login.','success')
        return _rb.redirect(_rb.url_for('admin_users'))
    return admin_user_reset_password

