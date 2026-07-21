import { useEffect, useState } from 'react';
import Hoverable from '../components/Hoverable';
import { Fade, PageTitle, Eyebrow } from '../components/ui';
import { useApp } from '../hooks/useApp';
import { color, line, font } from '../styles/tokens';

export default function Profile() {
  const { t, lang, cabinet } = useApp();
  const me = cabinet.me;
  const [profileEditOpen, setProfileEditOpen] = useState(false);
  const [pwChangeOpen, setPwChangeOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [curPassword, setCurPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    setEmail(me?.email || me?.owner_email || '');
  }, [me?.email, me?.owner_email]);

  const inputStyle = {
    width: '100%', background: color.bgPanel, border: `1px solid ${line.soft}`,
    borderRadius: 10, padding: '10px 12px', color: color.text,
    fontFamily: font.body, fontSize: 12.5, outline: 'none', boxSizing: 'border-box',
  };

  const saveEmail = async () => {
    if (!me?.is_workspace_owner) {
      cabinet.setError(lang === 'ru' ? 'Email может менять только владелец' : 'Only the owner can change email');
      return;
    }
    await cabinet.saveProfileEmail(email.trim());
    setProfileEditOpen(false);
  };

  const savePassword = async () => {
    if (newPassword.length < 8) {
      cabinet.setError(lang === 'ru' ? 'Пароль минимум 8 символов' : 'Password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      cabinet.setError(lang === 'ru' ? 'Пароли не совпадают' : 'Passwords do not match');
      return;
    }
    await cabinet.changeAccountPassword(curPassword, newPassword);
    setCurPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setPwChangeOpen(false);
  };

  const card = {
    background: color.surface, border: `1px solid ${line.hair}`, borderRadius: 16, padding: 18, marginBottom: 12,
  };

  return (
    <Fade data-screen-label="Профиль">
      <div style={{ maxWidth: 560 }}>
        <div style={{ marginBottom: 16 }}>
          <PageTitle style={{ marginBottom: 5 }}>{t.navProfile}</PageTitle>
          <div style={{ fontSize: 12.5, color: color.textDim }}>{t.profileDesc}</div>
        </div>

        <div style={card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontWeight: 800, fontSize: 14 }}>{t.accountData}</span>
            {me?.is_workspace_owner && (
              <Hoverable
                as="span"
                style={{ fontSize: 11.5, fontWeight: 700, color: color.lime, cursor: 'pointer' }}
                hover={{ color: color.limeHi }}
                onClick={() => setProfileEditOpen((v) => !v)}
              >
                ✎ {t.editProfile}
              </Hoverable>
            )}
          </div>
          <Eyebrow style={{ marginBottom: 7 }}>{t.email}</Eyebrow>
          {profileEditOpen ? (
            <>
              <input value={email} onChange={(e) => setEmail(e.target.value)} style={{ ...inputStyle, marginBottom: 10 }} />
              <Hoverable
                style={{
                  background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
                  borderRadius: 9, padding: '9px 20px', fontSize: 12, fontWeight: 800, color: color.lime, cursor: 'pointer',
                  display: 'inline-block',
                }}
                hover={{ background: 'rgba(215,244,82,.2)' }}
                onClick={() => void saveEmail()}
              >
                {t.save}
              </Hoverable>
            </>
          ) : (
            <div style={{ fontSize: 13, color: color.textMid }}>{me?.email || me?.owner_email || '—'}</div>
          )}
        </div>

        <div style={card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <span style={{ fontWeight: 800, fontSize: 14 }}>{t.changePassword}</span>
            <Hoverable
              as="span"
              style={{ fontSize: 11.5, fontWeight: 700, color: color.lime, cursor: 'pointer' }}
              hover={{ color: color.limeHi }}
              onClick={() => setPwChangeOpen((v) => !v)}
            >
              ✎ {t.editProfile}
            </Hoverable>
          </div>
          {pwChangeOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <Eyebrow size={9} spacing="1.6px" style={{ marginBottom: 6 }}>{t.curPassword}</Eyebrow>
                <input type="password" value={curPassword} onChange={(e) => setCurPassword(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <Eyebrow size={9} spacing="1.6px" style={{ marginBottom: 6 }}>{t.newPassword}</Eyebrow>
                <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} style={inputStyle} />
              </div>
              <div>
                <Eyebrow size={9} spacing="1.6px" style={{ marginBottom: 6 }}>{t.confirmPassword}</Eyebrow>
                <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} style={inputStyle} />
              </div>
              <Hoverable
                style={{
                  alignSelf: 'flex-start', background: 'rgba(215,244,82,.12)', border: '1px solid rgba(215,244,82,.3)',
                  borderRadius: 9, padding: '9px 20px', fontSize: 12, fontWeight: 800, color: color.lime, cursor: 'pointer',
                }}
                hover={{ background: 'rgba(215,244,82,.2)' }}
                onClick={() => void savePassword()}
              >
                {t.save}
              </Hoverable>
            </div>
          )}
        </div>
      </div>
    </Fade>
  );
}
