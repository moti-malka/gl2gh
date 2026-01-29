/**
 * User Profile Page
 */
import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../components/Toast';
import { Loading } from '../components/Loading';
import './ProfilePage.css';

export const ProfilePage = () => {
  const { user, updateProfile, changePassword } = useAuth();
  const [editing, setEditing] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  
  const [profileData, setProfileData] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
  });
  
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  
  const toast = useToast();

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const result = await updateProfile(profileData);
    
    if (result.success) {
      toast.success('Profile updated successfully');
      setEditing(false);
    } else {
      toast.error(result.error);
    }
    
    setLoading(false);
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    
    if (passwordData.new_password !== passwordData.confirm_password) {
      toast.error('Passwords do not match');
      return;
    }
    
    if (passwordData.new_password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    
    setLoading(true);
    
    const result = await changePassword({
      current_password: passwordData.current_password,
      new_password: passwordData.new_password,
    });
    
    if (result.success) {
      toast.success('Password changed successfully');
      setChangingPassword(false);
      setPasswordData({
        current_password: '',
        new_password: '',
        confirm_password: '',
      });
    } else {
      toast.error(result.error);
    }
    
    setLoading(false);
  };

  if (!user) {
    return <Loading message="Loading profile..." />;
  }

  return (
    <div className="page profile-page">
      <div className="page-header">
        <h1>User Profile</h1>
        <p className="page-subtitle">Manage your account settings</p>
      </div>

      <div className="profile-sections">
        <div className="section">
          <div className="section-header">
            <h2>Profile Information</h2>
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="btn btn-sm"
              >
                Edit Profile
              </button>
            )}
          </div>
          <div className="content">
            {editing ? (
              <form onSubmit={handleProfileUpdate}>
                <div className="form-group">
                  <label htmlFor="full_name">Full Name</label>
                  <input
                    id="full_name"
                    type="text"
                    value={profileData.full_name}
                    onChange={(e) =>
                      setProfileData({ ...profileData, full_name: e.target.value })
                    }
                    disabled={loading}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="email">Email</label>
                  <input
                    id="email"
                    type="email"
                    value={profileData.email}
                    onChange={(e) =>
                      setProfileData({ ...profileData, email: e.target.value })
                    }
                    disabled={loading}
                  />
                </div>

                <div className="form-actions">
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false);
                      setProfileData({
                        full_name: user.full_name || '',
                        email: user.email || '',
                      });
                    }}
                    className="btn btn-secondary"
                    disabled={loading}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={loading}
                  >
                    {loading ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="profile-info">
                <div className="info-item">
                  <strong>Username:</strong>
                  <span>{user.username}</span>
                </div>
                <div className="info-item">
                  <strong>Email:</strong>
                  <span>{user.email}</span>
                </div>
                <div className="info-item">
                  <strong>Full Name:</strong>
                  <span>{user.full_name || 'Not set'}</span>
                </div>
                <div className="info-item">
                  <strong>Role:</strong>
                  <span className={`role-badge role-${user.role}`}>
                    {user.role}
                  </span>
                </div>
                <div className="info-item">
                  <strong>Status:</strong>
                  <span className={`status-badge ${user.is_active ? 'status-active' : 'status-inactive'}`}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="section">
          <div className="section-header">
            <h2>Change Password</h2>
            {!changingPassword && (
              <button
                onClick={() => setChangingPassword(true)}
                className="btn btn-sm"
              >
                Change Password
              </button>
            )}
          </div>
          <div className="content">
            {changingPassword ? (
              <form onSubmit={handlePasswordChange}>
                <div className="form-group">
                  <label htmlFor="current_password">Current Password</label>
                  <input
                    id="current_password"
                    type="password"
                    value={passwordData.current_password}
                    onChange={(e) =>
                      setPasswordData({ ...passwordData, current_password: e.target.value })
                    }
                    required
                    disabled={loading}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="new_password">New Password</label>
                  <input
                    id="new_password"
                    type="password"
                    value={passwordData.new_password}
                    onChange={(e) =>
                      setPasswordData({ ...passwordData, new_password: e.target.value })
                    }
                    required
                    disabled={loading}
                    minLength="8"
                  />
                  <span className="form-hint">
                    Password must be at least 8 characters
                  </span>
                </div>

                <div className="form-group">
                  <label htmlFor="confirm_password">Confirm New Password</label>
                  <input
                    id="confirm_password"
                    type="password"
                    value={passwordData.confirm_password}
                    onChange={(e) =>
                      setPasswordData({ ...passwordData, confirm_password: e.target.value })
                    }
                    required
                    disabled={loading}
                  />
                </div>

                <div className="form-actions">
                  <button
                    type="button"
                    onClick={() => {
                      setChangingPassword(false);
                      setPasswordData({
                        current_password: '',
                        new_password: '',
                        confirm_password: '',
                      });
                    }}
                    className="btn btn-secondary"
                    disabled={loading}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={loading}
                  >
                    {loading ? 'Changing...' : 'Change Password'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="password-info">
                <p>Click "Change Password" to update your password.</p>
                <p className="hint">
                  Make sure to use a strong password with at least 8 characters.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
